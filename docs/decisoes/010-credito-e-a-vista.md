# 010. Meios de pagamento: crédito tem fatura, o resto é à vista

- **Data:** 2026-11-25
- **Status:** ativa

## Contexto

O modelo da 004 só conhecia cartão de crédito (fechamento, vencimento, fatura). Mas débito, Pix e dinheiro são pagos na hora e não entram em fatura nenhuma. Tratar "débito" como um cartão com fatura (como os primeiros testes faziam) daria totais errados.

## Decisão

- O cadastro passa a ser de **meio de pagamento** (`payment_method`), com dono, nome, apelidos e tipo: `credito`, `debito`, `pix` ou `dinheiro`.
- Só `credito` tem `closing_day`, `due_day`, faturas e parcelas (decisões 004 e 008). Para os outros, os dois dias são nulos (restrição no banco).
- Compra à vista vale na data da compra, sem fatura e sem parcelas. Ela conta no total do mês de cada pessoa (quem deve quanto).
- "Nx" num meio à vista não vira parcelas: o campo fica marcado como duvidoso na conferência.
- Na frase, o tipo sai do apelido do meio ("débito", "pix", "nubank"), sem IA.

## Consequência

- O código de cálculo (`billing.py`) não muda: ele só é chamado para crédito.
- As telas mostram duas coisas: a fatura de cada cartão de crédito e os gastos à vista do mês, os dois com total por pessoa.
