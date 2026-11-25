# 003. Provedor de IA escolhido por variável de ambiente

- **Data:** 2026-11-25
- **Status:** ativa

## Contexto

O app precisa de IA disponível 24 horas e de graça. Rodar modelo próprio não cabe em hospedagem grátis. Ao mesmo tempo, desenvolver e rodar evals centenas de vezes gastaria a cota grátis, e as frases reais não deveriam sair da máquina nos testes. Os termos do Gemini grátis e do Mistral Experiment permitem usar os dados para treino.

## Decisão

- O código fala com a IA por uma interface só (transcrição e extração), e `AI_PROVIDER` escolhe a implementação.
- Produção: Groq (Whisper com `language="pt"` para áudio e um modelo com JSON schema para extração). O nome do modelo também vem de variável, porque muda com frequência.
- Desenvolvimento e evals: Ollama local com um modelo pequeno; Whisper local quando fizer sentido.
- Gemini grátis e Mistral Experiment não entram, por causa dos termos de treino. **TODO: confirmar** no console da Groq os limites do plano grátis e a opção de retenção zero antes do primeiro deploy.

## Consequência

- Trocar de provedor é configuração, não código.
- Os evals rodam contra os dois provedores e o README pode mostrar a comparação.
