# 007. Modo sem IA e ordem de construção

- **Data:** 2026-11-25
- **Status:** ativa

## Contexto

O valor do Nico para quem usa está na fatura: cartão com fechamento e vencimento, parcelas nos meses certos, total por pessoa (decisão 004). A IA só deixa o lançamento mais rápido. Se ela for obrigatória, o app para quando os provedores grátis caírem, e quem não quer mandar os gastos para um provedor de IA fica sem opção. Na pesquisa, um bot sem nenhuma IA, que aprende palavras com o uso, tem mais estrelas que quase todos os bots com LLM (`docs/PESQUISA.md`).

## Decisão

- O app funciona inteiro **sem IA**. Cada pessoa escolhe nas configurações se a IA fica ligada; sem ela, nada sai do app para provedor de IA.
- O modo sem IA tem duas entradas:
  - **Formulário rápido:** cartão, dono e data já preenchidos com o último usado; só valor e descrição são obrigatórios.
  - **Frase curta com regras, sem IA:** um parser em Python entende o formato simples "valor descrição [cartão] [Nx]", por exemplo "120 mercado nubank 3x". O nome do cartão vem da tabela de apelidos. O que o parser não entender abre o formulário com o texto preenchido.
- Para áudio sem IA, o caminho é o ditado do teclado do celular, que vira texto e passa pelo parser.
- O parser de regras também é a primeira etapa com a IA ligada: frase simples não gasta chamada de IA; só o que ele não entende vai para a cascata (decisão 006).
- **Ordem de construção:** primeiro o núcleo sem IA (cartões, faturas, parcelas, total por pessoa, formulário, parser de regras, login); depois a IA por cima.
- Os evals comparam o parser de regras com cada provedor de IA nas mesmas frases. É isso que mede o ganho real da IA.

## Consequência

- O app tem valor desde a primeira versão, mesmo antes da IA.
- A IA precisa provar nos evals que acerta mais que as regras nas frases difíceis (vários gastos numa frase, "ontem", "metade é de fulano"); se não provar, continua opcional.
