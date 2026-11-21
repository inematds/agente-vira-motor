#!/usr/bin/env bash
# motor-modelo.sh — esqueleto de um MOTOR: a tarefa repetitiva em passos fixos.
# Regra: tudo que é igual toda vez é script; o modelo entra SÓ no passo que precisa julgar,
# com o menor modelo+esforço que a medição (medir.py) aprovou; todo passo tem conferência;
# se falhar, grava UMA linha no FALHAS.md e para (nada de "tentar de novo até dar").
set -euo pipefail
PASTA=${1:?pasta do trabalho}; FALHAS=${FALHAS:-$PASTA/FALHAS.md}
MODELO=${MODELO:-haiku}; ESFORCO=${ESFORCO:-low}     # escolhido pela medição, não pelo gosto
falhou() { printf '| %s | %s | %s | %s |\n' "$(date +%F)" "$1" "${2:-pendente}" "${3:-infra}" >> "$FALHAS"; echo "Falhou: $1" >&2; exit 1; }

# 1. Coletar (script) ─────────────────────────────────────────────
[ -d "$PASTA/entrada" ] || falhou "motor: pasta entrada/ ausente em $PASTA" "criar entrada/ antes de rodar" infra
# 2. Preparar (script): o que é sempre igual — formatos, nomes, tamanhos
# 3. Julgar (modelo, curto e com formato fixo de resposta)
# resposta=$(claude -p --model "$MODELO" --effort "$ESFORCO" --tools "" --output-format text < "$PASTA/pedido.txt")
# 4. Conferir (script): a resposta tem o formato? os números batem com a entrada?
# python3 conferir.py "$PASTA" || falhou "motor: conferência reprovou a resposta" "ver conferir.py" prompt
# 5. Entregar (script) e avisar: "Terminei: ..."
echo "Terminei: motor em $PASTA"
