"""fontes.py — lê os quatro registros de erro de um ou vários projetos.

Formatos (uma linha por ocorrência, mais recente no topo):
  FALHAS.md          | data | o que quebrou | menor correção | prompt|infra |
  LIMITES.md         | data | o que tentei | o que barrou | contorno | proposta | aberto|aceito |
  revisor-falhas.md  ## AAAA-MM-DD HH:MM · fluxo · título · nota N [· 🧑 crítica do dono]
                     - **Motivo:** ...
  LESSONS.md         - regra em uma linha ... (DD/MM/AAAA)  ou  (AAAA-MM-DD)

Só Python 3, sem rede, sem dependência.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import pathlib
import re
import unicodedata

NOMES = {"FALHAS.md": "falha", "LIMITES.md": "limite", "revisor-falhas.md": "revisor", "LESSONS.md": "licao"}
PULAR = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next"}

RE_LINHA = re.compile(r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|(.+)\|\s*$")
RE_REV = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})(?:\s+\d{2}:\d{2})?\s+·\s+(.+)$")
RE_DATA_BR = re.compile(r"\((?:[^()]*?)(\d{1,2})/(\d{1,2})/(\d{4})\)")
RE_DATA_ISO = re.compile(r"\((?:[^()]*?)(\d{4})-(\d{2})-(\d{2})\)")

STOP = set("""
a o e de da do das dos em no na nos nas um uma uns umas que se por para pra com sem mais menos ao aos à às ou
foi era ser ter tem sua seu suas seus isso este esta esse essa como quando onde não nao já ja só so até ate
depois antes sobre entre também tambem mesmo cada todo toda todos todas pelo pela pelos pelas lhe ele ela eles
the and for with from that this was were into nos pelo vez vezes porque mas nem quem qual quais
""".split())


@dataclasses.dataclass
class Registro:
    tipo: str            # falha | limite | revisor | licao
    data: dt.date
    texto: str           # o que quebrou / o que tentei / motivo / regra
    projeto: str
    arquivo: str
    causa: str = ""      # prompt | infra | prompt + infra (falha)
    status: str = ""     # aberto | aceito (limite)
    nota: float | None = None   # nota do revisor
    dono: bool = False   # crítica do dono (revisor)
    fluxo: str = ""      # fluxo do revisor (explicavideo, r7ex...)
    detalhe: str = ""    # o que barrou (limite) / correção (falha)
    _chave: frozenset | None = dataclasses.field(default=None, repr=False, compare=False)

    def chave(self) -> frozenset:
        if self._chave is None:
            self._chave = frozenset(palavras(self.texto + " " + self.detalhe))
        return self._chave


def palavras(texto: str) -> set[str]:
    t = unicodedata.normalize("NFKD", texto.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return {w for w in re.findall(r"[a-z][a-z0-9_.-]{3,}", t) if w not in STOP}


def parecido(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _data(s: str) -> dt.date | None:
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        return None


def ler_arquivo(caminho: pathlib.Path, projeto: str) -> list[Registro]:
    tipo = NOMES.get(caminho.name)
    if not tipo:
        return []
    try:
        linhas = caminho.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    regs: list[Registro] = []
    arq = str(caminho)
    if tipo in ("falha", "limite"):
        for ln in linhas:
            m = RE_LINHA.match(ln.strip())
            if not m or not (d := _data(m.group(1))):
                continue
            cols = [c.strip() for c in m.group(2).split("|")]
            if not cols or cols[0].startswith("---"):
                continue
            r = Registro(tipo, d, cols[0], projeto, arq)
            if tipo == "limite" and len(cols) >= 2:
                r.detalhe = cols[1]
            if tipo == "falha" and len(cols) >= 3:
                r.causa = cols[-1].lower()
            if tipo == "limite" and len(cols) >= 2:
                r.status = cols[-1].lower()
            regs.append(r)
    elif tipo == "revisor":
        atual: Registro | None = None
        for ln in linhas:
            m = RE_REV.match(ln.strip())
            if m and (d := _data(m.group(1))):
                partes = [p.strip() for p in m.group(2).split("·")]
                nota = None
                for p in partes:
                    mn = re.match(r"nota\s+(\d+(?:[.,]\d+)?)", p)
                    if mn:
                        nota = float(mn.group(1).replace(",", "."))
                atual = Registro(tipo, d, " · ".join(partes[1:2]) or partes[0], projeto, arq,
                                 nota=nota, dono="crítica do" in ln, fluxo=partes[0])
                regs.append(atual)
            elif atual and ln.strip().startswith("- **Motivo:**"):
                atual.texto = ln.split("**Motivo:**", 1)[1].strip() or atual.texto
    elif tipo == "licao":
        for ln in linhas:
            s = ln.strip()
            if not s.startswith("- "):
                continue
            d = None
            if (m := RE_DATA_ISO.search(s)):
                d = _data(f"{m.group(1)}-{m.group(2)}-{m.group(3)}")
            elif (m := RE_DATA_BR.search(s)):
                try:
                    d = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
                except ValueError:
                    d = None
            if d:
                regs.append(Registro(tipo, d, s[2:], projeto, arq))
    return regs


def achar_arquivos(raiz: pathlib.Path, profundidade: int = 2) -> list[pathlib.Path]:
    """Os quatro arquivos na raiz e nos projetos até `profundidade` níveis abaixo."""
    achados: list[pathlib.Path] = []

    def andar(p: pathlib.Path, nivel: int) -> None:
        for nome in NOMES:
            f = p / nome
            try:
                if f.is_file():
                    achados.append(f)
            except OSError:   # pasta sem permissão (ex.: volume de banco de dados)
                pass
        if nivel >= profundidade:
            return
        try:
            filhos = sorted(x for x in p.iterdir() if x.is_dir() and x.name not in PULAR and not x.name.startswith("."))
        except OSError:
            return
        for x in filhos:
            andar(x, nivel + 1)

    andar(raiz, 0)
    return achados


def ler_tudo(raiz: pathlib.Path, profundidade: int = 2) -> list[Registro]:
    raiz = raiz.expanduser().resolve()
    regs: list[Registro] = []
    for f in achar_arquivos(raiz, profundidade):
        rel = f.parent.relative_to(raiz)
        projeto = str(rel) if str(rel) != "." else raiz.name
        regs.extend(ler_arquivo(f, projeto))
    # a mesma linha em duas cópias do projeto (ex.: pasta -publico, espelho em output/) conta uma vez só
    vistos: set[tuple] = set()
    unicos = []
    for r in regs:
        k = (r.tipo, r.data, r.texto.strip().lower())
        if k not in vistos:
            vistos.add(k)
            unicos.append(r)
    return unicos


def ja_aconteceu(novo: Registro, antigos: list[Registro], limiar: float = 0.34) -> list[Registro]:
    """Registros anteriores (falha/limite/revisor) parecidos com `novo`."""
    k = novo.chave()
    return [a for a in antigos if a is not novo and a.data <= novo.data and a.tipo != "licao"
            and parecido(k, a.chave()) >= limiar]


def agrupar(regs: list[Registro], limiar: float = 0.34) -> list[list[Registro]]:
    """Agrupa registros parecidos (gulosamente, do mais recente ao mais antigo)."""
    grupos: list[tuple[set[str], list[Registro]]] = []
    for r in sorted(regs, key=lambda x: x.data, reverse=True):
        k = r.chave()
        for chave, membros in grupos:
            if parecido(k, chave) >= limiar:
                membros.append(r)
                break
        else:
            grupos.append((k, [r]))
    return [m for _, m in grupos]
