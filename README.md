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
│   └── schema-model.md         # Arquitetura dos contratos tipados, invariantes e JSON Schema
├── src/                        # Código-fonte da orquestração, agentes, evaluation e LLM
│   └── committee/
│       ├── agents/             # Agentes especializados executáveis
│       ├── evaluation/         # Framework de avaliação deliberativa (12 critérios)
│       ├── llm/                # Abstração de LLM, Mock e Google Gemini Provider
│       ├── orchestration/      # AgentRunner, ContextBuilder e Orchestrator
│       ├── event_store.py      # Event Store SQLite/WAL append-only
│       └── state_machine.py    # Máquina de estados finitos e quality gates
├── agents/                     # Prompts declarativos em Markdown para cada agente
├── schemas/                    # Contratos tipados em Pydantic v2 e validações
├── tests/                      # Suíte de testes automatizados (unitários, evaluation, llm)
├── scripts/                    # Scripts utilitários e smoke tests
└── decisions/                  # Registro das deliberações e decisões geradas
```

---

## 6. Integração com Provedores LLM (Google Gemini)

O AI Committee integra o **Google Gemini** como provedor de LLM através da biblioteca oficial `google-genai` com **Structured Output** compulsório validado por schemas Pydantic (sem parsing por regex).

### 6.1. Configuração de Variáveis de Ambiente

Para utilizar o provedor real do Gemini, configure a chave de API no seu terminal:

```bash
export GEMINI_API_KEY="sua-chave-de-api-aqui"
```

Variáveis opcionais de configuração:
```bash
export LLM_PROVIDER="gemini"            # Default: gemini
export GEMINI_MODEL="gemini-2.5-flash"   # Default: gemini-2.5-flash
export GEMINI_TIMEOUT_SECONDS="60.0"     # Default: 60.0
```

> **Aviso de Segurança**: Nunca comite chaves de API no código. O AI Committee aplica mascaramento compulsório em logs e sanitização automática de mensagens de erro para evitar vazamento de credenciais.

### 6.2. Smoke Test Controlado

Para verificar a comunicação com o Gemini de forma isolada (executando apenas o `ArchitectAgent` sem persistir sessões no Event Store):

```bash
export GEMINI_API_KEY="sua-chave-de-api-aqui"
PYTHONPATH=. .venv/bin/python scripts/smoke_test_gemini.py
```

### 6.3. Execução de Testes

```bash
# Executar todos os testes determinísticos (sem consumo de API nem custo de tokens)
PYTHONPATH=. .venv/bin/pytest -v

# Executar testes unitários do provedor Gemini (com mocks e simulação de retry/timeout)
PYTHONPATH=. .venv/bin/pytest -v tests/test_gemini_provider.py

# Executar teste de integração real opt-in (com chamada à API do Gemini)
RUN_LIVE_LLM_TESTS=1 GEMINI_API_KEY="sua-chave" PYTHONPATH=. .venv/bin/pytest -v tests/integration/test_gemini_live.py
```

Consulte [docs/llm-provider.md](docs/llm-provider.md) para detalhes da arquitetura de LLM, adaptação de schemas e telemetria.
