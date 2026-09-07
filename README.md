# AI Committee

> **Plataforma de deliberação técnica e estratégica multiagente orientada a rigor analítico, rastreabilidade e mentoria contínua.**

---

## 1. Visão Geral

O **AI Committee** é uma plataforma concebida para transformar a interação entre engenheiros/gestores e inteligências artificiais. Em vez de operar como um assistente convencional de resposta única — propenso à adulação (*sycophancy*), simplificações perigosas e falta de contraditório —, o AI Committee submete problemas reais a um comitê estruturado de especialistas virtuais dotados de papéis e vieses intencionalmente antagônicos.

### O Papel do Usuário Humano
O AI Committee **não substitui o usuário na tomada de decisão**. A responsabilidade e o poder de decisão final permanecem 100% com o ser humano. O objetivo do comitê é:
* Desmontar a complexidade do problema;
* Revelar pontos cegos operacionais e arquiteturais;
* Explicitar os trade-offs reais de cada alternativa;
* Capacitar o usuário a raciocinar sobre problemas semelhantes por meio de mentoria integrada.

---

## 2. Princípios Fundamentais

1. **Deliberação Estruturada** em vez de resposta única.
2. **Vieses Funcionais Diferenciados** entre os membros do comitê.
3. **Discordância Fundamentada** é ativamente encorajada.
4. **Consenso Nunca é Forçado**; bifurcações legítimas são explicitadas.
5. **Fatos, Premissas, Hipóteses e Desconhecidos** são formalmente segregados.
6. **Não Alucinação**: o sistema não inventa informações de contexto.
7. **Explicitação de Lacunas**: ausência de dados críticos é apontada imediatamente.
8. **Soberania do Usuário Humano**: o comitê propõe e elucida, o usuário decide.
9. **Rastreabilidade Compulsória**: todo resultado registra por que foi escolhido e por que outros foram rejeitados.
10. **Trade-offs Explícitos**: nenhuma solução é vendida como perfeita ou isenta de custos.
11. **Gatilhos Objetivos de Reavaliação**: decisões definem formalmente quando devem ser revisadas.
12. **Finalidade Pedagógica Permanente**: o usuário deve aprender os fundamentos do problema.

---

## 3. O Comitê Especializado

O sistema conta com 6 papéis com responsabilidades bem demarcadas:

| Papel | Foco Principal | O que Penaliza |
| :--- | :--- | :--- |
| **Facilitador** | Condução do debate, estruturação, moderação, validação de portais de qualidade | Consenso artificial, desvio de escopo, confusão entre fatos e premissas |
| **Arquiteto** | Longevidade, resiliência, modularidade, escalabilidade, sustentabilidade | Soluções frágeis, acoplamento excessivo, decisões difíceis de reverter |
| **Pragmático** | Simplicidade, rapidez de entrega, baixo custo, KISS, YAGNI | Overengineering, abstrações prematuras, complexidade operacional |
| **Auditor / SRE** | Confiabilidade, segurança, observabilidade, SPOFs, riscos, custos ocultos | Otimismo ingênuo, pontos únicos de falha, falta de plano de contingência |
| **Decisor** | Síntese do debate, recomendação fundamentada, trade-offs, honestidade (`INSUFFICIENT_EVIDENCE`) | Escolhas binárias ingênuas, decisões baseadas em scores arbitrários |
| **Mentor** | Extração de aprendizado, fundamentos técnicos, guia de estudo, conexões teóricas | Respostas superficiais, foco exclusivo no resultado sem ensinar o raciocínio |

Consulte [AGENTS.md](AGENTS.md) para a especificação completa e regras permanentes de cada agente.

---

## 4. O Fluxo de Deliberação em 7 Fases

O protocolo do comitê opera como uma máquina de deliberação estruturada de 7 fases:

```
[ Usuário + Problema Bruto ]
         │
         ▼
[ Fase 0: Investigação ] ────────► Facilitador + Usuário (Fatos, Restrições, Premissas, Desconhecidos)
         │
         ├───► [ Arquiteto ]     (Proposta A: Longevidade, modularidade, resiliência)
    (Divergência
       Cega)
         └───► [ Pragmático ]    (Proposta B: Simplicidade, KISS, YAGNI, velocidade)
                     │
                     ▼
[ Fase 2: Confronto ] ───────────► Auditor / SRE (Ataque adversarial, SPOFs, riscos, custos ocultos)
                     │
                     ▼
[ Fase 3: Defesa & Refinamento ] ► Arquiteto & Pragmático (Respostas a riscos, refinamento v2)
                     │
                     ▼
[ Fase 4: Convergência ] ────────► Facilitador (DeliberationSynthesis: mapeamento sem preferência)
                     │
                     ▼
[ Fase 5: Decisão ] ─────────────► Decisor (DecisionRecord: Recomendação OU Insufficient Evidence)
                     │
                     ▼
[ Fase 6: Reflexão ] ────────────► Mentor (LearningReport: conceitos, lacunas e guia de estudo)
                     │
                     ▼
  [ Dossiê de Decisão + Material Pedagógico (COMPLETED) ]
```

---

## 5. Estrutura do Workspace e Documentação Técnica

```
.
├── AGENTS.md                   # Regras permanentes, mandatos e governança dos agentes
├── README.md                   # Visão geral, princípios e estrutura do repositório
├── docs/                       # Especificações arquiteturais e formais do protocolo
│   ├── product-vision.md       # Visão de produto, motivação, valor e métricas
│   ├── committee-protocol.md   # Protocolo das 7 fases de deliberação (Fases 0 a 6)
│   ├── context-visibility.md   # Matriz formal de visibilidade e isolamento de contexto
│   ├── state-machine.md        # Máquina de estados finitos (FSM), transições e gates
│   ├── message-protocol.md     # Envelopes de mensagem, catálogo de eventos e schemas
│   ├── test-scenarios.md       # 5 cenários de teste conceituais do comportamento da engine
│   ├── decision-model.md       # Modelo de rastreabilidade (13 perguntas) e formato de ADR
│   ├── schema-model.md         # Arquitetura dos contratos tipados, invariantes e JSON Schema
│   ├── evaluation-framework.md # Framework de avaliação analítica (12 critérios + 6 epistêmicos)
│   ├── llm-provider.md         # Abstração de provedores LLM (Gemini, OpenAI, Mock)
│   ├── epistemic-discipline.md # Diretrizes, taxonomia e avaliação de Disciplina Epistêmica
│   └── cli.md                  # Interface interativa CLI, comandos e diálogo humano
├── src/                        # Código-fonte da orquestração, agentes, evaluation e LLM
│   └── committee/
│       ├── agents/             # Agentes especializados executáveis
│       ├── cli/                # Interface CLI interativa, comandos, UI e renderizador Unicode
│       ├── evaluation/         # Framework de avaliação deliberativa (12 critérios + 6 epistêmicos)
│       ├── llm/                # Abstração agnóstica de LLM (Mock, Gemini, OpenAI)
│       ├── orchestration/      # AgentRunner, ContextBuilder e Orchestrator
│       ├── event_store.py      # Event Store SQLite/WAL append-only
│       └── state_machine.py    # Máquina de estados finitos e quality gates
├── agents/                     # Prompts declarativos em Markdown para cada agente
├── schemas/                    # Contratos tipados em Pydantic v2 e validações epistêmicas
├── tests/                      # Suíte de testes automatizados (245+ testes)
│   └── cli/                    # Testes unitários e negativos da interface CLI
├── scripts/                    # Scripts utilitários, CLI executável e smoke tests
└── decisions/                  # Registro das deliberações e decisões geradas
```

---

## 6. Integração com Provedores LLM (OpenAI e Google Gemini)

O AI Committee suporta múltiplos provedores reais de LLM mantendo arquitetura agnóstica através da abstração `LLMProvider`:
* **OpenAI**: Via SDK oficial `openai>=3.8.0`, utilizando primordialmente a **Responses API** e **Structured Outputs** nativos com schemas Pydantic estritos (`strict: True`).
* **Google Gemini**: Via SDK oficial `google-genai`, utilizando esquemas adaptados via `clean_schema_for_gemini()`.
* **Mock**: Provedor determinístico offline para testes e validação das 7 fases sem custos de API.

### 6.1. Configuração de Variáveis de Ambiente

Para utilizar a OpenAI:
```bash
export OPENAI_API_KEY="sk-..."
export LLM_PROVIDER="openai"            # Default: gemini
export OPENAI_MODEL="gpt-4o"            # Default: gpt-4o
export OPENAI_TIMEOUT_SECONDS="60.0"    # Default: 60.0
```

Para utilizar o Google Gemini:
```bash
export GEMINI_API_KEY="AIza..."
export LLM_PROVIDER="gemini"
export GEMINI_MODEL="gemini-flash-latest" # Default: gemini-flash-latest
export GEMINI_TIMEOUT_SECONDS="60.0"     # Default: 60.0
```

Para sobrescrever o modelo ativo independentemente do provedor:
```bash
export LLM_MODEL="gpt-4o-mini"          # Sobrescreve o default do provider ativo
```

> **Aviso de Segurança**: Chaves de API nunca são commitadas nem exibidas em logs. O sistema aplica mascaramento compulsório (`sk-p...2345` / `AIza...3210`) e sanitização automática de segredos em mensagens de erro e exceções.

### 6.2. Smoke Tests Controlados

Para verificar a comunicação com um provedor de forma isolada (executando apenas o `ArchitectAgent` sem persistir sessões no Event Store):

```bash
# Smoke Test Epistemic Discipline (Mock determinístico)
PYTHONPATH=. .venv/bin/python scripts/smoke_test_epistemic.py --mock

# Smoke Test Epistemic Discipline (OpenAI real)
export OPENAI_API_KEY="sk-..."
PYTHONPATH=. .venv/bin/python scripts/smoke_test_epistemic.py

# Smoke Test OpenAI
export OPENAI_API_KEY="sk-..."
PYTHONPATH=. .venv/bin/python scripts/smoke_test_openai.py

# Smoke Test Google Gemini
export GEMINI_API_KEY="AIza..."
PYTHONPATH=. .venv/bin/python scripts/smoke_test_gemini.py
```

### 6.3. Execução de Testes Automatizados

```bash
# Executar todos os testes da suíte determinística (200 testes coletados)
PYTHONPATH=. .venv/bin/pytest -v

# Executar testes da camada de Disciplina Epistêmica
PYTHONPATH=. .venv/bin/pytest -v tests/test_epistemic_schemas.py tests/test_epistemic_discipline.py

# Executar testes dos 14 cenários de benchmark
PYTHONPATH=. .venv/bin/pytest -v tests/evaluation/test_scenarios.py

# Executar testes unitários do provedor OpenAI
PYTHONPATH=. .venv/bin/pytest -v tests/test_openai_provider.py

# Executar testes de substituição agnóstica de provedores
PYTHONPATH=. .venv/bin/pytest -v tests/test_provider_substitution.py

# Executar testes unitários do provedor Gemini
PYTHONPATH=. .venv/bin/pytest -v tests/test_gemini_provider.py

# Executar testes de integração reais opt-in
RUN_LIVE_LLM_TESTS=1 OPENAI_API_KEY="sk-..." PYTHONPATH=. .venv/bin/pytest -v tests/integration/test_openai_live.py
RUN_LIVE_LLM_TESTS=1 GEMINI_API_KEY="AIza..." PYTHONPATH=. .venv/bin/pytest -v tests/integration/test_gemini_live.py
```

Consulte [docs/epistemic-discipline.md](docs/epistemic-discipline.md) para detalhes da taxonomia epistêmica, critérios analíticos e mandates anti-sofisticação por padrão.
Consulte [docs/llm-provider.md](docs/llm-provider.md) para detalhes da arquitetura de provedores, Responses API, taxonomia de erros e telemetria.

---

## 7. Interface Interativa CLI

O AI Committee oferece uma interface interativa de terminal (`scripts/run_committee.py`) com renderização em caracteres Unicode e suporte completo a controle humano (*Human-in-the-Loop*):

```bash
# Executar modo demonstração (cenário pronto com Mock offline)
PYTHONPATH=. .venv/bin/python scripts/run_committee.py --example --mock

# Executar modo interativo (com entrada manual do problema)
PYTHONPATH=. .venv/bin/python scripts/run_committee.py --mock

# Executar com OpenAI em tempo real
export OPENAI_API_KEY="sk-..."
export LLM_PROVIDER="openai"
PYTHONPATH=. .venv/bin/python scripts/run_committee.py
```

### Comandos Disponíveis na CLI
* `help`: Exibe o catálogo de comandos.
* `status`: Exibe o estado atual da FSM e artefatos gerados.
* `context`: Visualiza o `ProblemContext` ativo (fatos, premissas, restrições).
* `events`: Exibe a trilha de auditoria append-only gravada no `EventStore`.
* `pause` / `resume`: Pausa ou retoma o fluxo da deliberação.
* `contest <id>`: Contesta e rejeita ou modifica uma premissa provisória.
* `revise`: Rejeita a recomendação formulada e reabre a Fase 1 com novas restrições.
* `abort`: Cancela e encerra a sessão imediatamente.

Consulte [docs/cli.md](docs/cli.md) para a documentação detalhada da interface interativa.
