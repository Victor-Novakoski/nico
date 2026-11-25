# 001. PWA e um backend só, em Python

- **Data:** 2026-11-25
- **Status:** ativa

## Contexto

Quem mais precisa do app usa Android, não usa Telegram e não tem tempo de abrir um app complicado. Um bot de WhatsApp oficial tem custo e burocracia. A parte de IA (extração, evals) é o foco de estudo e fica melhor em Python. Dois backends (por exemplo Go + Python) dobrariam a hospedagem grátis e cada um poderia dormir.

## Decisão

- App como PWA (React + Vite + TypeScript), instalado pelo navegador do celular. No Android, o microfone grava pelo `MediaRecorder` e o áudio vai para o backend.
- Um backend só, em FastAPI com Pydantic, que faz a extração com IA e todos os cálculos.
- Banco no Neon (Postgres grátis, acorda em milissegundos).
- Hospedagem grátis sem dormir. A primeira opção é a Vercel com funções Python; **TODO: confirmar** limites (tamanho do upload de áudio, tempo de execução) antes do primeiro deploy. O Render grátis dorme e leva cerca de 1 minuto para acordar, então fica só como reserva.

## Consequência

- Uma linguagem a menos para hospedar e testar.
- No iPhone, o PWA instalado tem bugs de microfone conhecidos; se um dia houver usuária de iPhone, o ditado do teclado vira o caminho principal.
- Se o cálculo de faturas crescer muito, um serviço separado pode voltar, com uma decisão nova.
