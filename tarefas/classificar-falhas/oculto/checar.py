#!/usr/bin/env python3
"""Nota 0–10 = acertos / total. O modelo nunca vê este arquivo nem o gabarito."""
import json, pathlib, re, sys
gab = json.loads((pathlib.Path(__file__).parent / "gabarito.json").read_text())
txt = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
m = re.search(r"\[[^\[\]]*\]", txt, re.S)
try:
    resp = [str(x).strip().lower() for x in json.loads(m.group(0))] if m else []
except Exception:
    resp = []
ok = sum(1 for a, b in zip(resp, gab) if a == b)
print(json.dumps({"acertos": ok, "total": len(gab), "nota": round(10 * ok / len(gab), 1), "formato_ok": len(resp) == len(gab)}))
