# Limites dos planos grátis

Lido nas páginas oficiais em 25/11/2026. Planos grátis mudam: **rever em 25/02/2027** ou antes de pôr no ar. O uso esperado é de cerca de 20 lançamentos por dia.

## Hospedagem: Vercel Hobby

Fonte: [Python runtime](https://vercel.com/docs/functions/runtimes/python), [limites](https://vercel.com/docs/functions/limitations), [Hobby](https://vercel.com/docs/plans/hobby).

- FastAPI é suportado (Python 3.12 por padrão).
- Corpo da requisição: até **4,5 MB** no Hobby. Áudio de 30 s comprimido (Opus ou AAC, que é o que o `MediaRecorder` gera) cabe com folga; WAV não. O app nunca envia WAV.
- Até 300 s por execução, 2 GB de memória.
- Por mês: 1 milhão de invocações, 4 horas de CPU ativa, 100 GB de transferência. Estourou, espera 30 dias.
- Não confirmado nas páginas lidas: se a função tem cold start longo e as regras de uso comercial (o projeto é pessoal).

## IA: Groq

Fonte: [limites](https://console.groq.com/docs/rate-limits), [dados](https://console.groq.com/docs/your-data).

- A tabela lida mostra os limites do plano Developer; a aba do plano grátis não foi lida. Como referência: Whisper com 2 mil requisições e 28.800 segundos de áudio por dia; `openai/gpt-oss-20b` com mil requisições por dia.
- Não guarda os dados da inferência por padrão; logs de erro ou abuso por até 30 dias. Qualquer cliente pode ligar **Zero Data Retention** em Data Controls: ligar antes de usar.
- A página não diz com todas as letras se os dados são usados para treino.

## IA: Cloudflare Workers AI

Fonte: [preço](https://developers.cloudflare.com/workers-ai/platform/pricing/), [limites](https://developers.cloudflare.com/workers-ai/platform/limits/), [uso de dados](https://developers.cloudflare.com/workers-ai/platform/data-usage/).

- 10 mil "neurons" grátis por dia (zera às 00:00 UTC). Whisper large v3 turbo gasta cerca de 47 por minuto de áudio: 10 minutos por dia usam menos de 5% da cota.
- Diz com todas as letras que **não usa o conteúdo para treinar** modelos e não guarda entradas e saídas.
- Não confirmado: chamada por REST de fora de um Worker. Testar antes de pôr na cascata.

## IA: OpenRouter

Fonte: [limites](https://openrouter.ai/docs/api-reference/limits), [privacidade](https://openrouter.ai/docs/features/privacy-and-logging).

- Modelos `:free`: 20 por minuto e **50 por dia** sem créditos comprados (mil por dia com pelo menos 10 créditos, o que seria pago).
- Para não ir a provedor que coleta dados: `provider: { data_collection: "deny" }` na requisição ou na configuração da conta.
- Não confirmado: se os modelos grátis continuam disponíveis com essa restrição. Testar; se não funcionarem, o OpenRouter sai da cascata.
