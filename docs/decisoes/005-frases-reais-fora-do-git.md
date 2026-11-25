# 005. Frases reais fora do git; evals versionados só com frases inventadas

- **Data:** 2026-11-25
- **Status:** ativa

## Contexto

O jeito certo de medir a IA é um conjunto fixo de frases com a resposta esperada, rodado a cada troca de prompt ou modelo. As melhores frases de teste são as que quem usa o app fala de verdade, mas elas contêm gastos, valores e nomes da família, e o repositório é público.

## Decisão

- `evals/examples/` (versionado): frases inventadas, cada uma com o JSON esperado, cobrindo os casos difíceis (vírgula decimal, "3x", "ontem", dois cartões na mesma frase, "metade é de fulano").
- `evals/real/` (no `.gitignore`): 30 a 50 frases reais, em texto e áudio, no mesmo formato. Rodam só na máquina, de preferência com o provedor local (decisão 003).
- O relatório dos evals mostra só taxas de acerto por campo, nunca o conteúdo das frases reais.

## Consequência

- Ninguém além do dono roda os evals reais; a CI roda só os inventados.
- Antes de cada commit, conferir que nada de `evals/real/` foi adicionado.
