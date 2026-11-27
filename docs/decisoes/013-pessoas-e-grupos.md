# 013. Cada pessoa tem o seu espaço; grupos são o que se divide

- **Data:** 2026-11-26
- **Status:** ativa (substitui a ideia de que o banco inteiro é uma casa; ajusta a privacidade da renda da 012 e o "criadas pela casa" da 011)

## Contexto

Até aqui o Nico tratava o banco inteiro como uma casa só: todo mundo com login via todos os meios de pagamento, compras e faturas. O uso real é outro. Uma pessoa começa usando sozinha, depois divide gastos com os pais, mais tarde com quem mora junto (namorada, amigos de república), e pode estar em mais de um desses arranjos ao mesmo tempo. Ao mesmo tempo, o banco cobra a fatura de um cartão inteira de quem é o dono, misturando compras só dele com compras divididas. Apps de dividir conta (Splitwise, Tricount) resolvem a divisão, mas não a vida financeira de cada um; apps de controle pessoal fazem o contrário.

## Decisão

- **Espaço pessoal:** cada pessoa é dona dos seus meios de pagamento, contas fixas, renda e gastos pessoais. Só ela vê esse espaço, a não ser que escolha mostrar (abaixo). Quem usa o Nico sozinho só tem isso.
- **Grupo:** um conjunto de pessoas que divide gastos ("Casa dos pais", "Nós dois", "República"). Quem cria convida os outros por um convite de uso único com validade. Uma pessoa pode estar em vários grupos. Um grupo pode ter membro sem login (por exemplo, um pai que não usa o app), cadastrado por outro membro; esse membro pode depois ganhar login ao aceitar um convite.
- **Todo lançamento tem um escopo:** pessoal ou de um grupo. Gasto de grupo é dividido só entre membros daquele grupo, com pesos (como hoje em `purchase_share`); o padrão é partes iguais. Conta fixa também pode ser pessoal ou de um grupo (o aluguel é da casa). Renda é sempre pessoal.
- **O meio de pagamento continua sendo de uma pessoa.** A fatura do cartão mostra todas as compras do dono, pessoais e de grupos, com o valor cheio, porque é isso que o banco cobra. O grupo vê as próprias compras (descrição, valor, divisão, quem pagou), nunca as outras compras daquele cartão.
- **Saldo e acerto:** quem pagou um gasto de grupo adiantou a parte dos outros. O código calcula quanto cada membro deve a cada um (arredondamento da 008) e "acertar" registra um pagamento entre dois membros, que reduz o saldo. A IA não participa disso.
- **Privacidade por grupo, escolhida por cada membro:**
  - Gastos: "só os do grupo" (padrão) ou "todos os meus". Mostrar todos dá aos membros leitura dos gastos pessoais, nunca edição.
  - Renda: escondida (padrão) ou visível. Substitui a opção única de "mostrar minha renda para a casa" da 012: agora a escolha é feita em cada grupo. A regra da 012 continua: o grupo não vê total de entradas que deixe deduzir o valor de quem escondeu.
- **Quem altera:** gasto pessoal, só o dono. Gasto de grupo, quem lançou ou o dono do meio de pagamento; os outros membros veem e podem conferir.
- **Sair do grupo:** só com o saldo da pessoa zerado. Os gastos do grupo continuam no grupo.
- **Categorias** (011) passam a pertencer a um escopo, como os lançamentos: as da pessoa e as de cada grupo.
- **Segurança:** o backend filtra toda consulta pelo escopo (dono ou membro do grupo); o que não é da pessoa responde 404, sem revelar que existe. Cada rota tem teste de isolamento entre duas pessoas e entre dois grupos. As mudanças de escopo, convite e cadastro passam pela revisão da skill `equipe-seguranca` antes do merge.

## Consequência

- O modelo de dados ganha grupo, membro, convite e acerto, e as tabelas de lançamento ganham escopo. As rotas que existem hoje mudam para filtrar por escopo.
- Vem antes de pôr no ar (marco 4): mudar o escopo com dados reais gravados é muito mais caro.
- Os dados de teste atuais migram assim: cada pessoa fica dona dos meios que já são dela; as pessoas existentes formam um grupo "Casa"; compra dividida entre mais de uma pessoa vai para esse grupo; compra de uma pessoa só fica pessoal.
- Cadastro deixa de ser só pelo terminal: quem recebe um convite cria o próprio login pelo app. Isso é uma superfície nova de ataque e entra na revisão de segurança.
- Fica de fora agora: pagamento real entre pessoas (Pix pelo app), lembrete de cobrança e conversão de moedas.
