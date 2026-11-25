# 002. A IA propõe, o código decide

- **Data:** 2026-11-25
- **Status:** ativa (o item "de quem é" foi substituído pela 009)

## Contexto

Na pesquisa de projetos parecidos (`docs/PESQUISA.md`), os erros mais caros foram valor errado salvo sem ninguém ver, vários gastos virando um só, vírgula decimal mal lida e IDs inventados pelo modelo. Saída estruturada garante a forma do JSON, não o sentido.

## Decisão

- O modelo devolve sempre uma **lista** de itens com descrição, valor, cartão, data, parcelas e pessoa. Qualquer campo pode vir vazio.
- Cada item traz o **trecho literal** da frase de onde saiu o valor. Um parser pt-BR em Python ("1.234,56", "12,50", "doze e cinquenta") confere o trecho; se divergir do valor do modelo, o campo fica destacado para a pessoa.
- Cartão e pessoa saem de listas fechadas enviadas no prompt; ID fora da lista é recusado no código. Apelidos de cartão ("cartão do fulano") ficam numa tabela, sem IA.
- O código converte valor para centavos inteiros e datas relativas ("ontem", "dia 10") para data real no fuso `America/Sao_Paulo`.
- Nada é salvo sem passar pela pessoa: o lançamento entra como "pendente" (para lançar rápido e conferir depois) ou "conferido". Na conferência, o destaque fica no campo que a IA chutou ou deixou vazio.
- "De quem é" vem preenchido com o dono do cartão e só muda quando a frase diz outra coisa.
- Se a IA falhar, abre o formulário manual com o texto já preenchido.

## Consequência

- A precisão da IA é medida por evals (decisão 005), não no olho.
- Todo cálculo de dinheiro tem teste unitário próprio, sem IA.
