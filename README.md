# Nico

Fale os gastos do jeito que vierem. O Nico monta os lançamentos, você confere, e ele mostra a fatura de cada cartão e quanto cada pessoa da casa deve.

> Em construção. Projeto pessoal e de estudo de IA aplicada (saída estruturada e evals).

## O problema

Apps de finanças são ótimos para quem tem paciência de lançar cada gasto à mão: valor, descrição, cartão, parcelas. Quem não tem tempo deixa para depois e, quando o cartão vence, passa uma hora juntando tudo, separando o que é seu nos cartões dos outros e tentando lembrar o que era aquela compra com nome de maquininha.

## A ideia

- **Lançar em segundos, por voz ou texto, vários gastos de uma vez:** "120 no mercado no cartão X em 3x, 15 de pão no débito e 30 de Uber, esse é meu".
- **A IA só propõe.** Ela devolve a lista de lançamentos; a pessoa confere na hora ou deixa como pendente para conferir depois. Valores, datas, parcelas e totais são sempre calculados por código.
- **Fatura de verdade:** cada cartão com dia de fechamento e vencimento, parcelas espalhadas nos meses certos e o total de cada pessoa, para comparar com o app do banco.

## Stack

PWA em React + Vite + TypeScript · FastAPI e Pydantic (Python) · IA em cascata de provedores grátis (Groq, Cloudflare Workers AI, OpenRouter), com Ollama local nos testes · PostgreSQL no Neon · tudo em planos grátis.

## Primeira versão

1. Cadastro de cartões (dono, fechamento, vencimento).
2. Uma caixa com texto ou microfone que vira uma lista de lançamentos para conferir.
3. Lançamento pendente ou conferido.
4. Fatura por cartão e por pessoa, com parcelas.
5. Login simples.
6. Evals com frases de exemplo, rodados a cada mudança de prompt ou modelo.

Depois: renda e resumo do mês; importar a fatura do banco e casar com o que foi lançado.

## Docs

- Como projetos parecidos fizeram e onde erraram: [`docs/PESQUISA.md`](docs/PESQUISA.md).
- Por que cada escolha: [`docs/decisoes/`](docs/decisoes/).
