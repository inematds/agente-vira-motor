# classificar-falhas — tabela refeita

| modelo | esforço | nota | segundos | tokens saída | custo equiv. US$ | custo por ponto |
|---|---|---:|---:|---:|---:|---:|
| sonnet | low | 9.4 | 4.2 | 271 | 0.0268 | 0.0029 |
| haiku | low | 9.2 | 6.8 | 1020 | 0.0019 | 0.0002 |
| sonnet | medium | 9.2 | 5.5 | 451 | 0.0284 | 0.0031 |
| sonnet | high | 9.2 | 6.3 | 556 | 0.0297 | 0.0032 |
| opus | low | 9.2 | 4.2 | 94 | 0.0503 | 0.0055 |
| opus | medium | 9.2 | 7.4 | 490 | 0.0582 | 0.0063 |
| opus | high | 9.2 | 7.8 | 556 | 0.0596 | 0.0065 |
| haiku | medium | 9 | 8 | 1286 | 0.0020 | 0.0002 |
| haiku | high | 9 | 13.3 | 2474 | 0.0026 | 0.0003 |

**Escolha:** haiku low — nota 9.2 (a melhor foi 9.4) por US$ 0.0019. A rodada mais cara (opus high) custou 31.6× mais e tirou 9.2.

Não rodou (erro, fora da média): fable high, fable low, fable medium — Fable 5.2 requires usage credits. Switch to another model, or manage usage credits at https://claude.ai/settings/usage?f
