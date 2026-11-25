# 011. Categorias em dois níveis, opcionais e sugeridas pelo histórico

- **Data:** 2026-11-25
- **Status:** ativa

## Contexto

Saber para onde vai o dinheiro ("quanto foi de combustível este mês") pede categorias. Mas a dor principal do app, a fatura por pessoa, funciona sem elas, e a pesquisa (`docs/PESQUISA.md`) mostrou que categorias, orçamentos e gráficos são onde apps pequenos incham. Apps que a família já usa organizam em categoria e subcategoria (por exemplo Transporte > Combustível, ou uma categoria para gastos com uma pessoa de fora da casa, com subcategorias Presentes e Alimentação).

## Decisão

- **Dois níveis, no máximo:** categoria e subcategoria. Um terceiro nível é recusado.
- **Criadas pela casa:** cada casa monta as suas. O app oferece um conjunto inicial no primeiro uso (Alimentação, Transporte > Combustível, Casa, Saúde, Lazer), que pode ser apagado.
- **Opcional em cada compra:** compra sem categoria continua válida; nada no cálculo de fatura depende dela.
- **Categoria não é "de quem é":** "de quem é" diz quem paga (decisão 009); a categoria diz para quê ou para quem foi o gasto. São campos separados.
- **Sugestão sem IA primeiro:** quando uma compra é conferida com categoria, o app guarda a relação entre as palavras da descrição e a categoria escolhida. Na próxima compra com essas palavras, a categoria vem sugerida com origem `historico`. Só sem histórico a IA pode sugerir, com origem `ia`, sempre de uma lista fechada. Nas duas, a sugestão aparece marcada para conferir.
- **Resumo do mês por categoria:** compra à vista conta no mês da compra; parcela no crédito conta no mês da fatura em que cai (o que de fato sai naquele mês).
- **Fica de fora:** orçamento por categoria, metas, alertas e gráficos elaborados.

## Consequência

- As categorias entram depois do núcleo no ar, no marco 5, junto do resumo do mês.
- Apagar uma categoria deixa as compras dela sem categoria, nunca as apaga; categoria com subcategorias só pode ser apagada depois delas.
