# Evals da IA

Frases com o rascunho esperado, para medir a IA a cada troca de prompt ou modelo (decisões 002 e 005).

## Arquivos

- `examples/frases.jsonl`: 30 frases **inventadas** (pessoas, cartões e lojas fictícios), versionadas. A CI roda só estas.
- `real/`: frases reais, no mesmo formato. **Fica fora do git** (está no `.gitignore`, decisão 005): nada de `real/` entra em commit.
- O leitor do formato é `backend/src/nico/eval_cases.py`. O runner que chama os provedores e compara campo a campo é `backend/src/nico/evals.py`.

## Formato

JSONL: um caso por linha, linhas em branco são ignoradas, campos desconhecidos são recusados. Exemplo (quebrado em várias linhas aqui; no arquivo é uma linha só):

```json
{
  "id": "c01",
  "text": "120 no Mercado Bom Preço no Cartão Azul",
  "today": "2026-11-25",
  "methods": [{"id": "azul", "aliases": ["cartão azul", "azul"], "type": "credito"}],
  "people": [{"id": "fulana", "names": ["Fulana"]}],
  "expected": [
    {
      "description": "mercado",
      "amount_cents": 12000,
      "method_id": "azul",
      "purchase_date": "2026-11-25",
      "installments": 1,
      "person_id": null
    }
  ],
  "tags": ["basico"]
}
```

- `today`, `methods` e `people` viram o contexto enviado ao provedor (as listas fechadas).
- `expected` é o que `schema.validate` produz a partir de uma extração correta, não o que o modelo escreve: valor em centavos, data calculada em relação a `today` (sem data na frase vale `today`), `method_id` e `person_id` das listas ou `null`.
- Sem meio na frase, `method_id` é `null`: o meio principal é aplicado depois, pelo código (decisão 009). Sem valor, `amount_cents` é `null`. Sem pessoa citada, `person_id` é `null`.
- "Nx" num meio à vista (débito, Pix, dinheiro) fica com `installments: 1` (decisão 010).
- `description` é só uma dica curta; a comparação será aproximada.
- "Metade é do Beltrano" hoje vira um item só com `person_id` do Beltrano: o schema da IA ainda não tem divisão entre pessoas. Quando tiver, estes casos (tag `metade`) mudam.
- Valor por extenso ("cento e vinte") fica `amount_cents: null`, porque `parse_brl` não lê extenso (ideia #51).
- `tags` dizem o que o caso testa (`virgula-decimal`, `milhar`, `parcelas`, `ontem`, `dia-n`, `dois-gastos`, `pessoa`, `sem-meio`, `sem-valor`...).

## Como rodar

A partir da raiz, com o venv do backend:

```
backend/.venv/bin/python -m nico.evals --set examples --provider rules
backend/.venv/bin/python -m nico.evals --set examples --provider ollama --limit 10
backend/.venv/bin/python -m nico.evals --set real --provider groq
```

- `--set examples` usa `examples/frases.jsonl`; `--set real` usa `real/frases.jsonl` (fora do git). `--provider` aceita `rules` (padrão), `ollama`, `groq`, `cloudflare` e `openrouter`; os de IA leem as variáveis de ambiente do próprio provedor. `--limit N` roda só os N primeiros casos.
- O relatório mostra acerto por campo, acerto exato (todos os campos menos a descrição), casos com número de rascunhos errado, falhas, tempo médio e a lista de casos com problema.
- A comparação alinha por posição (o 1º rascunho esperado contra o 1º previsto). A descrição é aproximada: vale se uma contém a outra, sem acento nem maiúscula.
- Com `--set real`, o relatório só mostra ids de casos e nomes de campos, nunca a frase nem a descrição. Falha de provedor aparece só pelo nome do tipo do erro.

## Validar

A partir da raiz do repositório:

```
backend/.venv/bin/pytest backend/tests/test_eval_cases.py -q
```

O teste confere que cada linha é JSON válido no formato, os ids são únicos, os meios e pessoas esperados existem nas listas do caso e os valores esperados aparecem na frase.
