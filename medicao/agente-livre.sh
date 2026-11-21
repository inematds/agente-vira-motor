#!/usr/bin/env bash
# agente-livre.sh — o MESMO resultado (o alerta do dia) feito de dois jeitos:
#   agente livre = claude -p recebe o pedido e sai procurando nos arquivos com as ferramentas que quiser
#   motor        = python3 alerta.py (script fixo, zero token)
# Pela assinatura (ANTHROPIC_API_KEY removida), numa config limpa (sem hooks/plugins/CLAUDE.md seus).
# Uso: medicao/agente-livre.sh <raiz-dos-projetos> [modelo] [esforco]
set -uo pipefail
AQUI=$(cd "$(dirname "$0")/.." && pwd)
RAIZ=$(cd "${1:?raiz dos projetos}" && pwd); MOD=${2:-sonnet}; ESF=${3:-medium}; TETO=${TETO:-1200}
ORIG=${CLAUDE_CONFIG_DIR:-$HOME/.claude}; CRED="$ORIG/.credentials.json"; [ -f "$CRED" ] || { echo "sem $CRED" >&2; exit 2; }
SAI="$AQUI/resultados/agente-livre-$(date +%Y%m%d-%H%M%S)"; mkdir -p "$SAI"
X=$(mktemp -d); mkdir -p "$X/cfg"; ln -s "$CRED" "$X/cfg/.credentials.json"
PEDIDO="Faça o alerta do dia dos meus projetos em $RAIZ: leia os arquivos FALHAS.md, LIMITES.md, revisor-falhas.md e LESSONS.md (na raiz e nos projetos), diga o que deu errado hoje e ontem e, principalmente, o que JÁ tinha acontecido antes (o erro que voltou), os limites ainda abertos e as notas baixas do revisor. Entregue um relatório curto em markdown."
ini=$(date +%s)
( cd "$RAIZ" && env -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN CLAUDE_CONFIG_DIR="$X/cfg" timeout "$TETO" \
    claude -p --model "$MOD" --effort "$ESF" --output-format json --strict-mcp-config --disable-slash-commands \
    --no-session-persistence --permission-mode default --allowedTools "Read Glob Grep Bash(grep:*) Bash(find:*) Bash(wc:*) Bash(head:*) Bash(ls:*)" \
    --max-turns 60 -- "$PEDIDO" < /dev/null ) > "$SAI/livre.json" 2> "$SAI/livre.err"
fim=$(date +%s)
[ -f "$X/cfg/.credentials.json" ] && [ ! -L "$X/cfg/.credentials.json" ] && cp -p "$X/cfg/.credentials.json" "$CRED"
rm -rf "$X"
m_ini=$(date +%s.%N); python3 "$AQUI/alerta.py" --raiz "$RAIZ" > "$SAI/motor.md"; m_fim=$(date +%s.%N)
python3 - "$SAI" "$((fim-ini))" "$(echo "$m_fim - $m_ini" | bc)" "$MOD" "$ESF" <<'EOF'
import json, sys, pathlib
sai, seg, mseg, mod, esf = pathlib.Path(sys.argv[1]), int(sys.argv[2]), float(sys.argv[3]), sys.argv[4], sys.argv[5]
try:
    j = json.loads((sai / "livre.json").read_text())
except Exception:
    j = {}
(sai / "livre.md").write_text(str(j.get("result", "")))
u = j.get("usage") or {}
ent = sum(u.get(k) or 0 for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
r = {"agente_livre": {"modelo": mod, "esforco": esf, "segundos": seg, "turnos": j.get("num_turns"),
     "tokens_entrada": ent, "tokens_saida": u.get("output_tokens"), "custo_usd": j.get("total_cost_usd"),
     "erro": j.get("is_error")},
     "motor": {"segundos": round(mseg, 2), "tokens": 0, "custo_usd": 0}}
(sai / "comparacao.json").write_text(json.dumps(r, indent=1))
print(json.dumps(r, indent=1))
EOF
