# 012. Contas fixas e renda: o que volta todo mês e o que entra

- **Data:** 2026-11-26
- **Status:** ativa, ajustada pela 013 (escopo pessoal ou de grupo e privacidade da renda por grupo)

## Contexto

Luz, água, internet, condomínio e financiamento voltam todo mês, com vencimento fixo. Se o app só conhece compras avulsas, o total do mês fica incompleto e a pessoa precisa lançar a mesma conta de novo a cada ciclo. Ao mesmo tempo, o mês da casa também tem entradas (salário, aluguel recebido, freela), e saber o que sobra para cada pessoa exige contar o que entrou.

Duas coisas precisam de regra explícita: como a conta fixa entra no mês sem virar lançamento errado, e como a renda aparece sem expor o valor de quem não quer mostrar.

## Decisão

### Contas fixas

- **Campos:** nome; dia de vencimento (1 a 31; em mês mais curto vale o último dia do mês); valor fixo em centavos **ou** "varia" (valor nulo); meio de pagamento; divisão por pessoa com pesos (igual à da tabela `purchase_share` das compras); parcelas opcionais (total e mês de início, para financiamento); ativa ou encerrada.
- **Exemplo fictício:** "Internet", vence dia 10, valor fixo, no crédito "Cartão Azul", dividida 50/50 entre Ana e Bruno.
- **Cálculo na hora:** o código calcula as contas de cada mês quando alguém abre a tela. Nada é gravado antes de a pessoa marcar.
- **Mês:** uma conta pertence ao mês do vencimento, não ao mês em que a pessoa a pagou.
- **Marcar como paga** é a pessoa confirmando:
  - conta de valor fixo já vem com o valor preenchido;
  - conta "varia" pergunta o valor e sugere a média dos 3 últimos pagamentos.
- Marcar cria uma **compra conferida** no meio da conta, com a divisão da conta e a data do pagamento, ligada à conta e ao mês. Desmarcar apaga essa compra.
- **Meio em crédito:** a compra cai na fatura daquele cartão (regras da 004 e da 008). No resumo do mês, ela conta na parte "cartões", nunca duas vezes: a conta fixa e a compra que ela gerou são uma só cobrança.
- **Meio à vista** (débito, Pix, dinheiro): a compra conta no total do mês à vista, como manda a 010.
- **Conta "varia" ainda não paga** entra no total do mês como **estimativa**, marcada com "~", para a tela não mostrar um total que parece fechado.
- **Parcelas (financiamento):** a conta tem total de parcelas e mês de início; cada mês do intervalo é uma parcela da conta.

### Renda

- **Renda fixa** (nome, dia, valor fixo ou "varia", de uma pessoa, por exemplo salário): aparece como "a receber" no mês. A pessoa marca como recebida pela bolinha, com o mesmo padrão de "marcar como paga".
- **Entrada avulsa** (autônomo, freela): é lançada pela frase ("recebi 350 do cliente"). A IA ou o parser só extrai os campos; a entrada aparece para conferência e só é salva depois que a pessoa confirma, como qualquer lançamento (decisão 002 e regra "nada é salvo sem passar pela pessoa").
- **Entrada não é compra:** não tem meio, parcela nem fatura. Fica numa tabela própria e conta no mês em que caiu.
- **Sobra da pessoa** = o que entrou para ela no mês − a parte dela nos gastos do mês (contas fixas, compras à vista e cartões). A sobra segue a mesma regra de privacidade da renda: se a renda está oculta, a sobra também está.
- **Escopo (013):** conta fixa é pessoal ou de um grupo (o aluguel é da casa); renda é sempre pessoal. Onde abaixo se lê "casa", leia "cada grupo da pessoa".
- **Privacidade da renda** (a 013 troca a opção única por uma escolha em cada grupo):
  - cada pessoa escolhe "mostrar minha renda para a casa". A opção vem **desligada** por padrão;
  - desligada, as outras pessoas veem só o nome da pessoa, sem valor, e a sobra dela também não aparece;
  - o total de entradas da casa soma **só** as pessoas que mostram a renda. Assim, o total não deixa deduzir o valor de quem escondeu;
  - a API aplica essa regra ao montar a resposta; a tela não é a única barreira.
- Vale para família e para quem usa o app sozinho (nesse caso, a própria pessoa é a única e vê tudo).

### Fora do escopo agora

- Lembrete ou notificação de vencimento.
- Reajuste automático de valor (aluguel, mensalidade).

## Consequência

- **Compra gerada pela conta é uma compra comum:** usa a mesma tabela de compras, de divisão e de parcelas. A conta fixa guarda só o vínculo (conta e mês) e a regra de cálculo; não existe um segundo lugar para somar valores.
- **Mês sem marcação:** a conta aparece como pendente, não como paga.
- **Mudar o dia de vencimento não move faturas passadas**, pela mesma regra da 004: a fatura de um cartão guarda as próprias datas.
- **Renda oculta não vaza pelo total:** a tela e a API usam a mesma regra, então não há total "da casa" que deixe deduzir valor escondido.
- **Estimativa não vira valor certo:** o "~" fica até a pessoa marcar a conta como paga; só então a compra conferida entra com o valor real.
- Nenhum cálculo de valor, data ou parcela é feito pela IA (decisão 002). Contas fixas são cálculo puro do código.
