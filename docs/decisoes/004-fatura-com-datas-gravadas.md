# 004. Fatura com datas gravadas, parcelas e total por pessoa

- **Data:** 2026-11-25
- **Status:** ativa

## Contexto

O valor do app está no cartão de crédito: saber em qual fatura cada compra cai, espalhar as parcelas e separar o que é de cada pessoa da casa, mesmo no cartão de outra pessoa. Apps grandes de código aberto (Actual, Firefly III) não têm data de fechamento nem parcelamento. Os apps brasileiros pequenos que acertam isso gravam as datas de cada fatura, para que mudar o dia do cartão não mexa no passado.

## Decisão

Modelo mínimo:
- **pessoa**; **cartão** (dono, dia de fechamento, dia de vencimento);
- **fatura** (cartão, competência, data de fechamento e de vencimento gravadas, status);
- **compra** (descrição, valor total em centavos, data, número de parcelas, status pendente/conferido);
- **parcela** (compra, fatura, valor em centavos), uma por fatura;
- **divisão** (compra, pessoa, cota).

O total de cada pessoa numa fatura é a soma das parcelas daquela fatura vezes a cota dela. A tela de fatura mostra o total esperado para comparar com o app do banco e quantos lançamentos ainda estão pendentes.

## Consequência

- **TODO: confirmar com faturas reais** o que acontece com compra feita no próprio dia do fechamento e para qual parcela vai o centavo que sobra na divisão. Pode variar por banco; vira regra testada quando confirmado.
- Renda, resumo do mês e importação de fatura ficam para depois, sem mudar esse modelo.
