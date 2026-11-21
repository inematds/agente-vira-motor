#!/usr/bin/env python3
"""medir.py — a MESMA tarefa em vários modelos e esforços, com nota dada por um checador oculto.

Responde: "qual é o modelo + esforço mais barato que ainda acerta esta tarefa repetitiva?"
Roda pela ASSINATURA (Claude Code `claude -p` ou Codex `codex exec`), nunca por chave de API:
a variável ANTHROPIC_API_KEY/OPENAI_API_KEY é removida do ambiente antes de cada rodada.

Uma tarefa é uma pasta com:
  pedido.txt          o pedido (igual para todos)
  entrada.json        (opcional) os dados, colados no fim do pedido
  oculto/checar.py    recebe o arquivo da resposta e imprime {"nota": 0–10, ...}; o modelo nunca vê

  python3 medir.py tarefas/classificar-falhas --modelos haiku,sonnet,opus --esforcos low,medium,high
  python3 medir.py tarefas/classificar-falhas --motor codex --modelos gpt-6-luna --esforcos low,medium
  python3 medir.py tarefas/classificar-falhas --simular          # sem modelo, para testar a cadeia

Grava resultados/<tarefa>-<data>/{rodadas.jsonl, tabela.md}.
"Custo" = o custo equivalente que o Claude Code informa (total_cost_usd). Na assinatura você não paga
por chamada, mas esse número é a melhor régua de quanto da sua cota cada rodada come.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import random
import shutil
import subprocess
import sys
import tempfile
import time

AQUI = pathlib.Path(__file__).resolve().parent


def montar_pedido(tarefa: pathlib.Path) -> str:
    p = (tarefa / "pedido.txt").read_text(encoding="utf-8")
    e = tarefa / "entrada.json"
    if e.is_file():
        p += "\n" + e.read_text(encoding="utf-8")
    return p


def env_assinatura() -> dict:
    env = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "OPENAI_API_KEY", "OPENROUTER_API_KEY"):
        env.pop(k, None)
    return env


def rodar_claude(pedido: str, modelo: str, esforco: str, teto: int) -> dict:
    """claude -p numa config limpa (sem hooks, plugins nem CLAUDE.md seus), só a credencial da assinatura."""
    origem = pathlib.Path(os.environ.get("CLAUDE_CONFIG_DIR", pathlib.Path.home() / ".claude")).expanduser()
    cred = origem / ".credentials.json"
    if not cred.is_file():
        raise SystemExit(f"sem {cred}: faça `claude` login pela assinatura antes")
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="medir-"))
    (tmp / "cfg").mkdir()
    (tmp / "cfg" / ".credentials.json").symlink_to(cred)
    (tmp / "w").mkdir()
    env = env_assinatura()
    env["CLAUDE_CONFIG_DIR"] = str(tmp / "cfg")
    cmd = ["claude", "-p", "--model", modelo, "--effort", esforco, "--output-format", "json",
           "--tools", "", "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence",
           "--max-turns", "3"]
    ini = time.time()
    try:
        cp = subprocess.run(cmd, input=pedido, capture_output=True, text=True, timeout=teto, cwd=tmp / "w", env=env)
        bruto = cp.stdout
    except subprocess.TimeoutExpired:
        bruto = ""
    seg = time.time() - ini
    novo = tmp / "cfg" / ".credentials.json"   # token renovado durante a rodada → devolve para a config original
    if novo.is_file() and not novo.is_symlink():
        shutil.copy2(novo, cred)
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        j = json.loads(bruto)
    except json.JSONDecodeError:
        return {"resposta": bruto[-2000:], "segundos": round(seg, 1), "erro": "saída não é JSON"}
    u = j.get("usage") or {}
    return {"resposta": j.get("result", ""), "segundos": round(seg, 1),
            "custo_usd": j.get("total_cost_usd"),
            "tokens_entrada": (u.get("input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0)
            + (u.get("cache_creation_input_tokens") or 0),
            "tokens_saida": u.get("output_tokens"), "erro": "" if not j.get("is_error") else str(j.get("result"))[:200]}


def rodar_codex(pedido: str, modelo: str, esforco: str, teto: int) -> dict:
    with tempfile.TemporaryDirectory(prefix="medir-cx-") as d:
        out = pathlib.Path(d) / "resposta.txt"
        cmd = ["codex", "exec", "-m", modelo, "-c", f"model_reasoning_effort={esforco}", "-s", "read-only",
               "--skip-git-repo-check", "--output-last-message", str(out), "-"]
        ini = time.time()
        try:
            cp = subprocess.run(cmd, input=pedido, capture_output=True, text=True, timeout=teto, cwd=d, env=env_assinatura())
            err = "" if cp.returncode == 0 else cp.stderr[-200:]
        except subprocess.TimeoutExpired:
            err = "timeout"
        seg = time.time() - ini
        resp = out.read_text(encoding="utf-8") if out.is_file() else ""
        tokens = None
        saida = "" if err == "timeout" else (cp.stdout + "\n" + cp.stderr)
        linhas = saida.splitlines()
        for i, ln in enumerate(linhas):   # o Codex imprime "tokens used" e o número na linha seguinte
            if "tokens used" in ln.lower():
                alvo = ln + " " + (linhas[i + 1] if i + 1 < len(linhas) else "")
                tokens = "".join(ch for ch in alvo.split("used", 1)[-1] if ch.isdigit()) or None
        return {"resposta": resp, "segundos": round(seg, 1), "custo_usd": None,
                "tokens_saida": int(tokens) if tokens else None, "erro": err}


def rodar_simulado(pedido: str, modelo: str, esforco: str, teto: int) -> dict:
    gab = json.loads((AQUI / "tarefas/classificar-falhas/oculto/gabarito.json").read_text())
    acerto = {"low": 0.6, "medium": 0.8, "high": 0.95}.get(esforco, 0.7)
    rnd = random.Random(f"{modelo}-{esforco}")
    resp = [g if rnd.random() < acerto else ("infra" if g == "prompt" else "prompt") for g in gab]
    return {"resposta": json.dumps(resp), "segundos": 0.0, "custo_usd": 0.0, "tokens_saida": 0, "erro": ""}


def checar(tarefa: pathlib.Path, resposta: str) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(resposta)
    try:
        cp = subprocess.run([sys.executable, "-I", str(tarefa / "oculto" / "checar.py"), f.name],
                            capture_output=True, text=True, timeout=60)
        return json.loads(cp.stdout.strip().splitlines()[-1])
    except Exception as e:  # checador quebrado = nota 0, nunca acerto
        return {"nota": 0.0, "erro_checador": str(e)[:200]}
    finally:
        os.unlink(f.name)


def tabela(todas: list[dict]) -> str:
    falhas = [r for r in todas if r.get("erro")]
    linhas = [r for r in todas if not r.get("erro")]
    if len(linhas) and len({(r["modelo"], r["esforco"]) for r in linhas}) < len(linhas):   # média das repetições
        grupos: dict = {}
        for r in linhas:
            grupos.setdefault((r["modelo"], r["esforco"]), []).append(r)
        media = lambda xs, k: (sum(x.get(k) or 0 for x in xs) / len(xs)) if xs else 0
        linhas = [{"modelo": m, "esforco": e, "nota": round(media(xs, "nota"), 1), "segundos": round(media(xs, "segundos"), 1),
                   "tokens_saida": round(media(xs, "tokens_saida")), "custo_usd": media(xs, "custo_usd") if xs[0].get("custo_usd") is not None else None,
                   "n": len(xs)} for (m, e), xs in grupos.items()]
    out = ["| modelo | esforço | nota | segundos | tokens saída | custo equiv. US$ | custo por ponto |",
           "|---|---|---:|---:|---:|---:|---:|"]
    for r in sorted(linhas, key=lambda x: (-(x["nota"] or 0), x.get("custo_usd") or 0)):
        c = r.get("custo_usd")
        cpp = f"{c / r['nota']:.4f}" if c and r["nota"] else "—"
        out.append(f"| {r['modelo']} | {r['esforco']} | {r['nota']:g} | {r['segundos']:g} | {r.get('tokens_saida') or '—'} | "
                   f"{f'{c:.4f}' if c is not None else '—'} | {cpp} |")
    validas = [r for r in linhas if r.get("custo_usd")]
    if validas:
        topo = max(r["nota"] for r in linhas)
        bons = [r for r in validas if r["nota"] >= topo - 0.5]
        barato = min(bons, key=lambda r: r["custo_usd"])
        caro = max(validas, key=lambda r: r["custo_usd"])
        out += ["", f"**Escolha:** {barato['modelo']} {barato['esforco']} — nota {barato['nota']:g} (a melhor foi {topo:g}) "
                f"por US$ {barato['custo_usd']:.4f}. A rodada mais cara ({caro['modelo']} {caro['esforco']}) custou "
                f"{caro['custo_usd'] / barato['custo_usd']:.1f}× mais e tirou {caro['nota']:g}."]
    if falhas:
        nao = sorted({f"{r['modelo']} {r['esforco']}" for r in falhas})
        out += ["", f"Não rodou (erro, fora da média): {', '.join(nao)} — {falhas[0]['erro'][:120]}"]
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tarefa")
    ap.add_argument("--motor", choices=["claude", "codex"], default="claude")
    ap.add_argument("--modelos", default="haiku,sonnet,opus")
    ap.add_argument("--esforcos", default="low,medium,high")
    ap.add_argument("--rep", type=int, default=1)
    ap.add_argument("--teto", type=int, default=600, help="segundos por rodada")
    ap.add_argument("--simular", action="store_true", help="não chama modelo (testa a cadeia)")
    ap.add_argument("--saida", help="pasta de resultados (padrão resultados/<tarefa>-<data>)")
    ap.add_argument("--tabela", metavar="PASTA", help="só refaz a tabela.md de uma pasta de resultados (rodadas.jsonl)")
    o = ap.parse_args(argv)
    if o.tabela:
        pasta = pathlib.Path(o.tabela)
        linhas = [json.loads(x) for x in (pasta / "rodadas.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
        md = f"# {pathlib.Path(o.tarefa).name} — tabela refeita\n\n" + tabela(linhas)
        (pasta / "tabela.md").write_text(md, encoding="utf-8")
        print(md)
        return 0
    tarefa = pathlib.Path(o.tarefa).resolve()
    if not (tarefa / "pedido.txt").is_file() or not (tarefa / "oculto" / "checar.py").is_file():
        print("a tarefa precisa de pedido.txt e oculto/checar.py", file=sys.stderr)
        return 2
    pedido = montar_pedido(tarefa)
    rodar = rodar_simulado if o.simular else (rodar_claude if o.motor == "claude" else rodar_codex)
    sai = pathlib.Path(o.saida) if o.saida else AQUI / "resultados" / f"{tarefa.name}-{dt.datetime.now():%Y%m%d-%H%M%S}"
    sai.mkdir(parents=True, exist_ok=True)
    linhas = []
    with open(sai / "rodadas.jsonl", "a", encoding="utf-8") as log:
        for rep in range(1, o.rep + 1):
            for m in o.modelos.split(","):
                for e in o.esforcos.split(","):
                    print(f"→ {m} {e} (rodada {rep})", file=sys.stderr, flush=True)
                    r = rodar(pedido, m, e, o.teto)
                    nota = checar(tarefa, r.get("resposta", ""))
                    linha = {"modelo": m, "esforco": e, "rep": rep, "nota": nota.get("nota", 0.0), **nota,
                             **{k: v for k, v in r.items() if k != "resposta"}, "resposta": r.get("resposta", "")[:500]}
                    log.write(json.dumps(linha, ensure_ascii=False) + "\n")
                    log.flush()
                    linhas.append(linha)
                    print(f"   nota {linha['nota']:g} · {linha['segundos']:g} s · US$ {linha.get('custo_usd')}", file=sys.stderr)
    md = f"# {tarefa.name} — {dt.date.today()} ({o.motor}{', simulado' if o.simular else ''})\n\n" + tabela(linhas)
    (sai / "tabela.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
