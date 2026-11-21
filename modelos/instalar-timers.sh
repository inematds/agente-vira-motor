#!/usr/bin/env bash
# Liga o alerta diário (08:00) e o aprendizado semanal (segunda 07:45) no systemd do usuário. Não precisa de sudo.
set -euo pipefail
D=$(cd "$(dirname "$0")" && pwd); U="$HOME/.config/systemd/user"; mkdir -p "$U"
KIT=$(cd "$D/.." && pwd)
for f in avm-alerta.service avm-alerta.timer avm-semana.service avm-semana.timer; do
  sed "s#%h/projetos/agente-vira-motor#$KIT#" "$D/$f" > "$U/$f"
done
systemctl --user daemon-reload
systemctl --user enable --now avm-alerta.timer avm-semana.timer
systemctl --user list-timers avm-alerta.timer avm-semana.timer --no-pager
echo "Para mandar o alerta para o celular: edite ENVIO= em $U/avm-alerta.service (o texto chega pelo stdin)."
