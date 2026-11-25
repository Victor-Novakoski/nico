# Nico

App de gastos (PWA) em que a pessoa fala ou escreve os gastos do jeito que vierem ("120 no mercado no cartão X em 3x e 15 de pão no débito"), a IA monta a lista de lançamentos para conferir, e o app mostra a fatura de cada cartão e quanto cada pessoa da casa deve. Projeto pessoal e de estudo de IA (saída estruturada e evals).

## Stack

PWA em React + Vite + TypeScript · um backend só em Python (FastAPI + Pydantic) · IA em cascata de provedores grátis: Groq, depois Cloudflare Workers AI e OpenRouter; Ollama local para desenvolver e para os evals · PostgreSQL no Neon · hospedagem grátis, a confirmar (ver `docs/decisoes/001`).

## Comandos

Backend (detalhes em `backend/CLAUDE.md`), a partir da raiz:

```
python3 -m venv backend/.venv && backend/.venv/bin/pip install -e "backend[dev]"
backend/.venv/bin/pytest backend -q
backend/.venv/bin/ruff check backend && backend/.venv/bin/ruff format --check backend
```

Web (`web/`, Node 22), a partir da raiz:

```
npm --prefix web ci
npm --prefix web run dev      # proxy de /api para localhost:8000
npm --prefix web run lint && npm --prefix web run format:check
npm --prefix web test && npm --prefix web run build
```

Evals (a partir da raiz; `--set real` lê `evals/real/frases.jsonl`, fora do git, e nunca imprime as frases):

```
backend/.venv/bin/python -m nico.evals --set examples --provider rules
backend/.venv/bin/python -m nico.evals --set examples --provider ollama --limit 10   # Ollama local
```

## Como se orientar

- Leia `docs/INDEX.md` e abra só o que a tarefa pede.
- Tarefas abertas são issues do GitHub (etiquetas `prioridade` e `ideia`).
- O porquê das escolhas está em `docs/decisoes/`; a pesquisa de projetos parecidos, em `docs/PESQUISA.md`.

## Como as tarefas andam

- Todo trabalho é uma issue pequena, no formato do modelo `.github/ISSUE_TEMPLATE/tarefa.md`: objetivo, arquivos, o que fazer, como testar, pronta quando, depende de. Cada uma cabe em 2 a 3 minutos de um subagente.
- **Tarefa grande demais:** antes de começar, quebre em issues menores no mesmo formato; a grande vira só uma lista que aponta para as pequenas.
- Etapas são os marcos (1. Núcleo sem IA, 2. App no celular, 3. IA opcional, 4. No ar, Depois). `prioridade` marca as próximas; `subagente` marca as que um subagente faz sozinho; `precisa do victor` marca o que só o dono faz (conta, senha, dado real).
- Pegue só issues cujas dependências já estão fechadas. Issues sem dependência entre si e sem arquivos em comum podem rodar em paralelo.
- A sessão principal planeja, cria as issues, revisa o diff e roda os testes antes de cada PR. Um PR por issue, com `Closes #N`.

### Subagentes em paralelo

- **Uma worktree por issue:** `git worktree add ~/projects/nico-wt/issue-N -b <tipo>/<nome> develop`. Cada subagente trabalha só na sua pasta e faz um commit, sem push; a sessão principal revisa, envia e abre o PR. Depois do merge: `git worktree remove` e apagar a branch local.
- **Um banco de teste por subagente:** a sessão principal sobe o Postgres (`docker compose up -d --wait`) e cria `nico_tN` com `docker compose exec -T db createdb -U nico nico_tN`; cada subagente usa só `NICO_TEST_DATABASE_URL=postgresql://nico@localhost:5433/nico_tN` e não roda `docker compose up/down`. Os testes recriam o schema, então dois agentes no mesmo banco se atropelam. No fim, `dropdb` e `docker compose down`.
- **Merge um PR por vez** e confira `gh pr view N --json state` = `MERGED` antes de fechar a issue. Dois PRs que mexem no mesmo arquivo (ex.: lista de dependências do `backend/pyproject.toml`) dão conflito: traga a `develop` para a branch, resolva, rode os testes, espere a CI.
- **`Closes #N` não fecha a issue** quando o PR entra na `develop` (só na branch padrão, `main`): feche à mão com `gh issue close N --comment "Feito no #PR (na develop)."`.
- Depois de cada leva, rode tudo na `develop` atualizada, com o banco ligado, e confira a CI da `develop`.

## Regras gerais (não quebrar)

- **A IA propõe, o código decide** (decisão 002). A IA só extrai os campos da frase. Valor em centavos inteiros, datas, parcelas, faturas e totais são calculados por código, nunca pelo modelo.
- **Nada é salvo sem passar pela pessoa.** O lançamento entra como "pendente" ou "conferido"; a IA nunca grava direto como certo.
- **A resposta da IA é uma lista**, mesmo com um gasto só. Cartão e pessoa vêm de uma lista fechada; ID que não existe é recusado no código.
- **Crédito tem fatura; débito, Pix e dinheiro são à vista** (decisão 010). Sem meio na frase, entra o principal da pessoa, sempre marcado como padrão; "de quem é" padrão é quem lançou (decisão 009).
- **Fatura guarda as próprias datas** de fechamento e vencimento: mudar o dia do cartão não altera faturas passadas (decisão 004).
- **Frases reais ficam fora do git** (decisão 005). Evals versionados usam só frases inventadas.
- **O app funciona sem IA** (decisão 007): formulário rápido e parser de regras para frases simples. A IA é opcional, desligável por pessoa, e só recebe o que o parser não entendeu. Construir o núcleo sem IA primeiro.
- **IA em cascata** (decisão 006): `AI_PROVIDERS` dá a ordem; se um provedor falhar (limite, erro, resposta inválida), o próximo tenta; se todos falharem, abre o formulário manual. Planos grátis que treinam com os dados (Gemini grátis, Mistral Experiment) não entram.
- Textos para pessoas (telas, docs) em português do Brasil; código, arquivos e identificadores em inglês.

## Git e PR

- Trabalhar a partir da `develop`; todo PR vai para a `develop`, nunca para a `main`. Push direto bloqueado na `main` e na `develop`; branch apagada após o merge.
- Conventional Commits. Branch com o tipo: `feat/…`, `fix/…`, `docs/…`.
- Nenhuma branch, commit ou PR com "claude" no nome. Se a ferramenta criar uma assim, renomeie antes do PR.
- Commits com a identidade do Victor (`Victor-Novakoski`), sem trailer `Co-Authored-By` de IA, sem link de sessão, sem assinatura de IA. Se a integração do GitHub puser o rodapé "Generated by Claude Code" no PR, remova.
- Um commit por tarefa, com testes, lint e formatação passando.

## Segurança e custo

- Segredo só em variável de ambiente: nunca em arquivo do repositório, flag, log, mensagem de erro ou doc (nem senha de teste; diga onde é definida). `.env.example` sem valores reais.
- **O repositório é público.** Nenhum dado pessoal real entra em código, docs, commits, issues ou PRs: gastos, valores, nomes da família, frases ditas por quem usa o app. Exemplos só com dados fictícios.
- Login obrigatório: dado financeiro nunca fica aberto na internet.
- Nada pago: hospedagem, banco, IA e domínio só em plano grátis. Se algo exigir custo, pare e pergunte.

## Manutenção dos docs

- Antes de uma tarefa, leia docs/INDEX.md e abra só o que ela pede.
- Ao terminar, se aprendeu algo não documentado que faria falta, registre no CLAUDE.md do módulo.
- Doc passou de ~150 linhas? Divida por subtema e atualize o INDEX.
- Decisão de arquitetura nova → arquivo novo em docs/decisoes/.
- Se o código contradiz o doc, o código vale: corrija o doc e avise.
- Faxina geral (skill `docs-projeto`, modo faxina) só no fim de cada marco, pela issue de faxina dele; não rode a skill a cada issue. No dia a dia basta o registro acima. Motivo: com muitos PRs pequenos, os docs ficam velhos aos poucos e só uma revisão do conjunto pega isso; rodar a skill a cada issue gasta tempo relendo o que acabou de ser escrito.
