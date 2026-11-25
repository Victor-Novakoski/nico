# 006. Cascata de provedores de IA

- **Data:** 2026-11-25
- **Status:** ativa (substitui a 003)

## Contexto

A decisão 003 escolhia um provedor por variável de ambiente. Mas planos grátis têm limite diário e caem de vez em quando, e quem usa o app não pode ficar sem lançar porque um provedor bateu o limite. Projetos parecidos usam uma cascata (por exemplo Groq → Gemini → OpenRouter → Ollama no [finance-ai](https://github.com/kelvin-amancio/finance-ai)).

## Decisão

- O código fala com a IA por duas interfaces (transcrição e extração). `AI_PROVIDERS` lista a ordem, por exemplo `groq,cloudflare,openrouter`. Se um provedor falhar, o próximo da lista tenta.
- **Quando passar para o próximo:** limite estourado (HTTP 429), erro do servidor (5xx), tempo esgotado ou resposta que não passa na validação Pydantic do schema. Erro de configuração (chave inválida, 401) não passa adiante: é erro e aparece no log.
- **Só entram provedores grátis que não treinam com os dados.** Candidatos:
  - Groq: Whisper e extração; primeiro da fila.
  - Cloudflare Workers AI: tem Whisper e modelos de texto no plano grátis; segundo.
  - OpenRouter: só modelos grátis que funcionam com o treino desligado; terceiro.
  - Ollama: só na máquina de desenvolvimento e nos evals; não atende o app no ar.
  - Gemini grátis e Mistral Experiment continuam fora (os termos permitem treino).
  - **TODO: confirmar** nos termos e no painel de cada um (limites grátis, retenção, treino) antes de pôr no ar.
- O nome do modelo de cada provedor vem de variável, porque muda com frequência.
- Cada lançamento guarda qual provedor e modelo respondeu (nunca o texto em log), para os evals e para achar problemas.
- Se todos falharem, abre o formulário manual com o texto ou a transcrição já preenchidos (decisão 002). O áudio fica na fila local e pode ser reenviado.
- Os evals rodam contra cada provedor da lista, para saber se o de reserva acerta o suficiente.

## Consequência

- Um provedor a mais é uma classe nova e uma linha na variável, sem mexer no resto.
- Modelos diferentes erram de jeitos diferentes; a conferência pela pessoa e a checagem do valor em código (decisão 002) continuam valendo para todos.
