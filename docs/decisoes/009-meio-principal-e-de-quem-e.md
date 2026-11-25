# 009. Meio de pagamento principal e "de quem é" padrão

- **Data:** 2026-11-25
- **Status:** ativa (substitui o item "de quem é" da 002)

## Contexto

Muita frase não diz o meio de pagamento ("30 uber"), e deixar o campo em branco toda vez cansa. Ao mesmo tempo, o erro mais grave visto na pesquisa foi lançar no cartão errado sem ninguém notar. A 002 dizia que "de quem é" vinha com o dono do cartão; mas quem usa o cartão de outra pessoa como principal teria todas as compras atribuídas ao dono, justamente o caso que o app quer separar.

## Decisão

- Cada pessoa pode ter um **meio de pagamento principal** (opcional), nas configurações dela.
- O parser de regras e a IA continuam devolvendo "sem meio" quando a frase não diz. Quem aplica o principal é a etapa de rascunho da API, que marca a origem do campo como `padrao` (diferente de `frase`).
- Na conferência, o meio que veio do padrão aparece com um aviso leve ("principal, você não disse"). Sem principal, o campo fica em branco para a pessoa escolher.
- Principal fixo, nunca "o último usado": o último usado muda sozinho e engana.
- **"De quem é" padrão = quem está lançando**, não o dono do cartão. Só muda quando a frase diz ("esse é de fulano", "metade é minha").

## Consequência

- A gravação da compra precisa saber quem lançou (usuário logado → pessoa).
- O total por pessoa da fatura passa a refletir quem comprou, mesmo no cartão de outra pessoa.
