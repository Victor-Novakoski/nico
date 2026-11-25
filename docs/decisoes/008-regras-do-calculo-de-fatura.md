# 008. Regras do cálculo de fatura

- **Data:** 2026-11-25
- **Status:** ativa

## Contexto

A decisão 004 definiu o modelo (cartão, fatura com datas gravadas, parcelas, divisão). Faltavam as regras de borda: compra no dia do fechamento, mês curto, para onde vai o centavo que sobra. Elas mudam de banco para banco e ainda não foram conferidas com faturas reais.

## Decisão

Implementado em `backend/src/nico/billing.py`:
- **Competência** é o mês do vencimento.
- **Dia maior que o mês** (31 em fevereiro, 31 em abril) vira o último dia do mês.
- **Mês do vencimento** sai dos dias configurados: se `due_day > closing_day`, vence no mesmo mês do fechamento; senão, no mês seguinte. Comparar as datas já ajustadas repetia competência (fecha 28 e vence 31: as faturas de fevereiro e de março saíam as duas como março).
- **Compra no dia do fechamento** entra na fatura seguinte (a compra cai na primeira fatura cujo fechamento é estritamente depois dela). *Suposição a confirmar.*
- **Parcelas:** divisão inteira em centavos; o centavo que sobra vai para a **primeira parcela** (100,00 em 3x = 33,34 + 33,33 + 33,33). *Suposição a confirmar.*
- **Divisão por pessoa:** pesos inteiros; cada um recebe o piso da sua parte e as sobras vão um centavo por vez em ordem alfabética do identificador. A soma sempre bate com o total.

## Consequência

- Num mês curto, fechamento e vencimento podem cair no mesmo dia (fecha 30 e vence 31: os dois em 28/02). É raro e não quebra o total.
- As duas suposições viram regra confirmada (ou mudam) com uma decisão nova depois de conferir faturas reais.
