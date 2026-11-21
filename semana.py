#!/usr/bin/env python3
"""semana.py — o aprendizado da semana: o que mais se repetiu, se a reincidência caiu e o que vira motor.

Compara os últimos 7 dias com os 7 anteriores e com a foto da semana passada (semana/AAAA-MM-DD.json).
Não chama modelo, não usa rede.

  python3 semana.py --raiz ~/projetos --pasta semana        # grava semana/AAAA-MM-DD.md e .json

A pergunta que ele responde: "o meu sistema errou MENOS o mesmo erro esta semana?"
Saída 0 = reincidência caiu ou ficou igual · 1 = subiu · 2 = erro de uso.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from motor import fontes  # noqa: E402

DEGRAU = [  # do mais forte ao mais fraco (mesma escada do agente-que-aprende)
    (8, "motor", "o passo vira script fixo: o modelo só entra onde precisa julgar"),
    (4, "trava", "gancho/validador que bloqueia o comando ou gera o que falta"),
    (2, "teste", "teste que reproduz o erro e falha se ele voltar"),
    (0, "lição", "uma linha no LESSONS.md (o degrau mais fraco: o modelo pode pular)"),
]


def degrau(vezes: int):
    for minimo, nome, como in DEGRAU:
        if vezes >= minimo:
            return nome, como
    return DEGRAU[-1][1:]


def janela(regs, ini, fim):
    return [r for r in regs if ini <= r.data <= fim]


def reincidencia(semana, antes, limiar):
    alvo = [r for r in semana if r.tipo != "licao"]
    if not alvo:
        return 0.0, 0
    rep = sum(1 for r in alvo if fontes.ja_aconteceu(r, antes, limiar))
    return rep / len(alvo), rep


def resumo(regs, hoje, limiar):
    ini = hoje - dt.timedelta(days=6)
    ini_ant = ini - dt.timedelta(days=7)
    sem = janela(regs, ini, hoje)
    ant = janela(regs, ini_ant, ini - dt.timedelta(days=1))
    taxa, rep = reincidencia(sem, [r for r in regs if r.data < ini], limiar)
    taxa_ant, _ = reincidencia(ant, [r for r in regs if r.data < ini_ant], limiar)
    c = collections.Counter(r.tipo for r in sem)
    c_ant = collections.Counter(r.tipo for r in ant)
    falhas = [r for r in sem if r.tipo == "falha"]
    causas = {"prompt": sum("prompt" in r.causa for r in falhas), "infra": sum("infra" in r.causa for r in falhas)}
    notas = collections.defaultdict(list)
    for r in sem:
        if r.tipo == "revisor" and r.nota is not None:
            notas[r.fluxo].append(r.nota)
    temas = []
    for g in fontes.agrupar([r for r in sem if r.tipo != "licao"], limiar):
        historico = fontes.ja_aconteceu(g[0], [r for r in regs if r.data < ini], limiar)
        total = len(g) + len(historico)
        if total >= 2:
            nome, como = degrau(total)
            temas.append({"assunto": g[0].texto[:160], "exemplo": g[0].detalhe[:120], "semana": len(g),
                          "antes": len(historico), "projetos": sorted({x.projeto for x in g + historico})[:6],
                          "desde": min(x.data for x in g + historico).isoformat(), "degrau": nome, "como": como})
    temas.sort(key=lambda t: -(t["semana"] * 3 + t["antes"]))
    return {
        "data": hoje.isoformat(), "inicio": ini.isoformat(),
        "contagem": dict(c), "contagem_anterior": dict(c_ant),
        "reincidencia": round(taxa, 3), "reincidencia_anterior": round(taxa_ant, 3), "repetidos": rep,
        "causas": causas, "donos": sum(1 for r in sem if r.tipo == "revisor" and r.dono),
        "notas": {k: round(statistics.mean(v), 1) for k, v in sorted(notas.items(), key=lambda kv: -len(kv[1]))[:8]},
        "temas": temas[:15], "licoes_novas": c.get("licao", 0),
    }


def texto(s, foto_passada) -> str:
    seta = lambda a, b: "⬇️ caiu" if a < b else ("⬆️ subiu" if a > b else "➡️ igual")
    pct = lambda x: f"{x * 100:.0f}%"
    out = [f"# Aprendizado da semana — {s['inicio']} a {s['data']}", "",
           f"**Reincidência: {pct(s['reincidencia'])}** ({s['repetidos']} registros que já tinham acontecido antes) · "
           f"semana anterior {pct(s['reincidencia_anterior'])} → {seta(s['reincidencia'], s['reincidencia_anterior'])}.",
           "", "A meta é uma só: o mesmo erro aparecer menos. Erro novo é aprendizado; erro repetido é desperdício.", "",
           "| | esta semana | semana anterior |", "|---|---:|---:|"]
    for t, nome in [("falha", "falhas"), ("limite", "limites"), ("revisor", "reprovações do revisor"), ("licao", "lições novas")]:
        out.append(f"| {nome} | {s['contagem'].get(t, 0)} | {s['contagem_anterior'].get(t, 0)} |")
    out += ["", f"Falhas por causa: prompt {s['causas']['prompt']} · infra {s['causas']['infra']}. "
            f"Críticas do dono: {s['donos']}.", ""]
    if s["notas"]:
        out += ["Nota média do revisor por fluxo: " + " · ".join(f"{k} {v:g}" for k, v in s["notas"].items()), ""]
    if foto_passada:
        antigos = {t["assunto"] for t in foto_passada.get("temas", [])}
        atuais = {t["assunto"] for t in s["temas"]}
        sumiu = antigos - atuais
        if sumiu:
            out += ["## ✅ Saiu da lista desde a semana passada (a trava funcionou ou o assunto parou)", ""]
            out += [f"- {a}" for a in sorted(sumiu)[:10]] + [""]
    out += ["## 🔁 O que mais se repetiu → o degrau certo", "",
            "| assunto | semana | antes | desde | vira |", "|---|---:|---:|---|---|"]
    for t in s["temas"]:
        ex = f" ({t['exemplo']})" if t["exemplo"] else ""
        out.append(f"| {t['assunto'][:90]}{ex[:70]} | {t['semana']} | {t['antes']} | {t['desde']} | **{t['degrau']}** |")
    out += ["", "Escada: **motor** (8+ vezes: o passo vira script, o modelo só julga) > **trava** (4+) > **teste** (2+) > lição.",
            "Escolha 1 a 3 assuntos do topo, suba o degrau e confira na semana que vem se saíram da lista.", ""]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raiz", default=".")
    ap.add_argument("--profundidade", type=int, default=2)
    ap.add_argument("--hoje", help="AAAA-MM-DD (para testar)")
    ap.add_argument("--limiar", type=float, default=0.34)
    ap.add_argument("--pasta", help="grava <pasta>/AAAA-MM-DD.md e .json e compara com a foto anterior")
    o = ap.parse_args(argv)
    raiz = pathlib.Path(o.raiz).expanduser()
    if not raiz.is_dir():
        print(f"raiz não existe: {raiz}", file=sys.stderr)
        return 2
    hoje = dt.date.fromisoformat(o.hoje) if o.hoje else dt.date.today()
    regs = [r for r in fontes.ler_tudo(raiz, o.profundidade) if r.data <= hoje]
    s = resumo(regs, hoje, o.limiar)
    passada = None
    if o.pasta:
        pasta = pathlib.Path(o.pasta).expanduser()
        pasta.mkdir(parents=True, exist_ok=True)
        fotos = sorted(p for p in pasta.glob("*.json") if p.stem < s["data"])
        if fotos:
            passada = json.loads(fotos[-1].read_text(encoding="utf-8"))
    md = texto(s, passada)
    if o.pasta:
        (pasta / f"{s['data']}.md").write_text(md, encoding="utf-8")
        (pasta / f"{s['data']}.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.stdout.write(md)
    return 1 if s["reincidencia"] > s["reincidencia_anterior"] else 0


if __name__ == "__main__":
    sys.exit(main())
