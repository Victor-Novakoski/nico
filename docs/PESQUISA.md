# Pesquisa: projetos parecidos

Feita em 25/11/2026 no GitHub e em posts ligados. Estrelas e datas mudam; o que importa são as lições.

## O espaço vazio

Nenhum projeto aberto junta as três partes do Nico. Elas existem separadas:

- **Bots de gasto por texto ou voz com LLM** (Telegram, WhatsApp, web): quase todos pequenos e de 2025–2026. Entendem "gastei 45 no ifood", mas nenhum liga a parcela ao fechamento do cartão.
- **Apps brasileiros de fatura**: modelam fechamento, vencimento e uma parcela por fatura, mas sem IA na entrada. Exemplo bem pensado: [Saldim](https://github.com/Eduarddoribeiro/saldim) (datas da fatura gravadas; compra de outra pessoa vira "a receber").
- **Apps de dividir contas** ([Spliit](https://github.com/spliit-app/spliit), [SplitPro](https://github.com/oss-apps/split-pro), [IHateMoney](https://github.com/spiral-project/ihatemoney)): calculam quem deve a quem, mas não conhecem cartão.
- Os grandes ([Actual](https://github.com/actualbudget/actual), [Firefly III](https://github.com/firefly-iii/firefly-iii)) não têm data de fechamento nem parcelamento. A IA entra por add-ons como o [actual-ai](https://github.com/sakowicz/actual-ai), que só categoriza.

## O que deu certo

- **IA propõe, código decide.** O modelo extrai "o que e quando"; centavos, datas e parcelas são código ([finance-ai](https://github.com/kelvin-amancio/finance-ai), [bot-financeiro-whatsapp](https://github.com/Kauesouzavr/bot-financeiro-whatsapp)).
- **Lista, nunca um objeto só.** Com schema de objeto único, "35 de gasolina e 12 de almoço" vira um registro de 47 ([SpendSnap](https://github.com/Kusagra9308/SpendSnap)). O [telegram-actual-llm-helper](https://github.com/deseven/telegram-actual-llm-helper) pede um array e injeta a data de hoje e as contas reais no prompt.
- **Conferir antes de salvar**, com edição de qualquer campo. Lançar como "não confirmado" e revisar depois ([Gullak](https://mrkaran.dev/posts/gullak/)).
- **Regras antes do LLM** e aprender com as correções de quem usa ([actual-budget-telegram-bot](https://github.com/bbharathbala/actual-budget-telegram-bot), sem IA nenhuma).
- **Data no fuso certo:** servidor em UTC lança o gasto da noite no dia seguinte.

## O que deu errado

- **Valor errado em silêncio:** um bot com LLM lançou um valor alto no cartão errado e o dono só viu meses depois.
- **Forma certa, sentido errado:** saída estruturada reduz erro de formato, mas não de significado. Vírgula decimal e IDs inventados aparecem em issues reais ([actual-ai #481](https://github.com/sakowicz/actual-ai/issues/481)).
- **Duplicatas por lentidão:** a resposta demora, a pessoa reenvia, o gasto entra duas vezes. Remédio: ID por envio e fila local.
- **Privacidade:** alguns planos grátis de IA usam os dados para treino.
- **Hábito:** apps de finanças retêm pouca gente depois de 30 dias. Lançar tem de levar segundos.
- **Escopo grande demais:** o Maybe Finance, com 54 mil estrelas, foi arquivado em 2025 porque a conta do negócio não fechou.
- **Ninguém publica evals** com frases reais e taxa de acerto.

## O que o Nico faz diferente

- Junta fala, fatura e divisão por pessoa num app só.
- Mede a IA com evals desde o primeiro dia (decisão 005).
- Mostra o total esperado de cada fatura para comparar com o banco: se bate, não precisa decifrar nome de maquininha.
