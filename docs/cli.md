# Interface CLI Interativa do AI Committee

A interface de Linha de Comando (CLI) interativa do **AI Committee** permite que um operador humano participe ativamente da deliberação técnica multiagente em tempo real, exatamente como em uma reunião executiva de engenharia.

---

## 1. Princípios de Design da Interface

1. **Zero Dependências Pesadas de UI**: A CLI utiliza exclusivamente caracteres Unicode padronizados (box-drawing e bordas arredondadas) e `textwrap` da biblioteca padrão do Python, sem depender de pacotes externos como `rich`.
2. **Soberania do Usuário Humano**: O operador humano detém o controle do ritmo: responde perguntas de investigação, pausa a deliberação, contesta premissas, aceita ou rejeita recomendações e solicita revisões.
3. **Imutabilidade e Rastreabilidade Integral**: Toda interação humana (respostas, contestações, revisões, cancelamentos) é modelada formalmente como comandos tipados em Pydantic (`HumanInterventionCommand`) e persistida atomicamente no `EventStore` append-only via `StateMachine`. Nenhuma transição de estado ocorre sem transição válida na FSM.
4. **Segurança de Segredos**: Toda a telemetria, erros e comandos mascaram chaves de API (`sk-...`, `AIza...`) e credenciais sensíveis.
5. **Isolamento de Contexto Mantido**: A CLI não expõe propostas cruzadas aos agentes durante a divergência cega (Fase 1).

---

## 2. Arquitetura de Componentes da CLI

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                           CommitteeCLIApp                               │
│  (Coordenador do loop deliberativo: fases, pausas e chamadas de agentes)│
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│    SessionUI    │         │ CommandHandler  │         │TerminalRenderer │
│  (Prompts I/O,  │◄───────►│(help, status,   │────────►│(Quadros Unicode,│
│   validações,   │         │ contest, revise,│         │ cards, tabelas, │
│  intervenções)  │         │ abort, pause)   │         │  telemetria)    │
└─────────────────┘         └─────────────────┘         └─────────────────┘
         │                           │
         └─────────────┬─────────────┘
                       ▼
          ┌──────────────────────────┐
          │   CommitteeOrchestrator  │
          │ (StateMachine/EventStore)│
          └──────────────────────────┘
```

### Componentes:
* **`TerminalRenderer`** (`src/committee/cli/renderer.py`): Formata cartões de investigação, painéis de propostas (incluindo a seção epistêmica com fatos, premissas, inferências e desconhecidos), relatórios de auditoria com SPOFs, síntese imparcial, veredito de decisão e telemetria.
* **`CommandHandler`** (`src/committee/cli/commands.py`): Processa comandos emitidos pelo usuário durante as etapas de deliberação.
* **`SessionUI`** (`src/committee/cli/session_ui.py`): Controla o diálogo interativo no terminal (coleta do problema, respostas a dúvidas, validação de entradas, normalização de campos desconhecidos para `UNKNOWN`).
* **`CommitteeCLIApp`** (`src/committee/cli/app.py`): Orquestrador do fluxo da CLI, conduzindo a sessão pelas Fases 0 a 6.

---

## 3. Comandos Interativos Disponíveis

Durante o avanço entre etapas, o usuário pode digitar comandos ou apenas pressionar `[Enter]` para continuar:

| Comando | Sintaxe | Descrição |
| :--- | :--- | :--- |
| `help` | `help` | Exibe o catálogo completo de comandos disponíveis. |
| `status` | `status` | Exibe o estado atual da FSM, fase ativa e contagem de artefatos. |
| `context` | `context` | Renderiza o `ProblemContext` atual (fatos, premissas, restrições, incógnitas). |
| `events` | `events` | Lista os eventos append-only gravados no `EventStore` SQLite com timestamp e autor. |
| `pause` | `pause` | Pausa o avanço automático da deliberação. |
| `resume` | `resume` / `continue` | Retoma a deliberação pausada. |
| `contest` | `contest [id]` | Contesta uma premissa (`Assumption`) adotada, permitindo rejeitá-la ou modificá-la. |
| `revise` | `revise` | Rejeita a recomendação formulada e retrocede a sessão para a Fase 1 com novas restrições. |
| `abort` | `abort [motivo]` | Cancela e encerra a sessão imediatamente (`USER_ABORT`), transicionando para `CANCELLED`. |

---

## 4. Como Executar a CLI

O script de entrada é `scripts/run_committee.py`.

### 4.1. Modo Demonstração Rápida (com Mock Provider)
Executa a deliberação com cenário padrão (problema de saturação de conexões em banco de dados), sem necessidade de chaves de API:

```bash
PYTHONPATH=. .venv/bin/python scripts/run_committee.py --example --mock
```

### 4.2. Modo Interativo Completo com Entrada Manual
Permite ao usuário definir o problema técnico, orçamento, equipe, prazos e critérios de sucesso:

```bash
PYTHONPATH=. .venv/bin/python scripts/run_committee.py --mock
```

### 4.3. Persistência em Arquivo SQLite (ou em Memória)
Por padrão, a CLI salva o log de eventos em `data/committee.db`. Para usar memória temporária ou um banco customizado:

```bash
# Banco em memória (volátil para testes rápidos)
PYTHONPATH=. .venv/bin/python scripts/run_committee.py --mock --memory

# Banco em caminho customizado
PYTHONPATH=. .venv/bin/python scripts/run_committee.py --mock --db /caminho/minha_sessao.db
```

### 4.4. Execução com Provedores Reais (OpenAI / Gemini)

Com a OpenAI:
```bash
export OPENAI_API_KEY="sk-..."
export LLM_PROVIDER="openai"
export OPENAI_MODEL="gpt-4o"
PYTHONPATH=. .venv/bin/python scripts/run_committee.py
```

Com o Google Gemini:
```bash
export GEMINI_API_KEY="AIza..."
export LLM_PROVIDER="gemini"
export GEMINI_MODEL="gemini-flash-latest"
PYTHONPATH=. .venv/bin/python scripts/run_committee.py
```

---

## 5. Smoke Test Integrado de Ponta a Ponta

Para validar a integridade de todas as 14 etapas (criação, investigação, divergência cega, confronto, defesas, convergência, decisão, mentoria, persistência SQLite, avaliação determinística de 18 critérios e replay bit a bit):

```bash
# Teste ponta a ponta com Mock determinístico
PYTHONPATH=. .venv/bin/python scripts/smoke_committee_openai.py --mock

# Teste ponta a ponta com OpenAI real
export OPENAI_API_KEY="sk-..."
PYTHONPATH=. .venv/bin/python scripts/smoke_committee_openai.py
```

---

## 6. Testes Automatizados da CLI

A suíte de testes da CLI cobre renderização, comandos, interface de diálogo e o fluxo integrado com 10 testes negativos estritos:

```bash
# Executar todos os testes específicos da CLI (34 testes)
PYTHONPATH=. .venv/bin/pytest -v tests/cli/

# Executar a suíte completa do AI Committee (245 testes)
PYTHONPATH=. .venv/bin/pytest -v
```
