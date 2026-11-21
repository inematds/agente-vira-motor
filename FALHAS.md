# FALHAS — agente-vira-motor

| data | o que quebrou | menor correção | prompt \| infra |
|---|---|---|---|
| 2026-11-20 | alerta.py quebrava ao varrer ~/projetos (PermissionError em pasta de banco de dados sem permissão) | try/except OSError no is_file | infra |
| 2026-11-20 | semana.py contava 170 linhas em dobro (cópias -publico e espelhos em output/) | deduplicar por (tipo, data, texto) | prompt |
| 2026-11-20 | medir.py: Fable entrava na tabela com nota 0 quando a rodada nem rodou (crédito) | rodada com erro sai da média e vai para "não rodou" | prompt |
