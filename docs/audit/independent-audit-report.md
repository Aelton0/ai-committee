# Relatório de Auditoria Técnica Independente — AI Committee

**Data da Auditoria**: 2026-09-07  
**Escopo**: Código-fonte completo, testes automatizados, documentação, schemas, e comportamento adversarial  
**Metodologia**: Inspeção estática de código, execução de testes, scripts adversariais, análise de consistência documentação ↔ código  
**Linhas analisadas**: ~16.500 (src: 7.101, schemas: 1.601, tests: 6.781)  
**Resultado dos testes**: 247 passed, 2 skipped, 0 failed

---

## Sumário Executivo

O projeto AI Committee demonstra uma arquitetura sofisticada e conceitualmente sólida em vários aspectos:

- **Isolamento de agentes**: A Divergência Cega e a separação contextual por fase estão rigorosamente implementadas e protegidas por invariantes em código.
- **Separação agente ↔ orquestrador**: Agentes não possuem acesso a `Session`, `StateMachine` ou `EventStore` — apenas recebem dicionários de contexto sanitizados.
- **Event Store**: Append-only com triggers SQLite, WAL mode, hashes de integridade e queries parametrizadas.
- **Schemas Pydantic v2**: Tipagem forte, `frozen=True`, `extra="forbid"`, validadores de modelo que bloqueiam estados inconsistentes.
- **Provider agnóstico**: O sistema funciona identicamente com Mock, OpenAI e Gemini sem nenhuma alteração de agente.

Porém, a auditoria identificou **25 findings**, categorizados abaixo por severidade. A maioria reflete lacunas entre a ambição conceitual da documentação e a realidade da implementação atual.

---

## Classificação dos Findings

| Severidade | Quantidade | Descrição |
| :--- | :---: | :--- |
| **CRITICAL** | 3 | Contradições fundamentais ou fragilidades que invalidam garantias de integridade do sistema |
| **HIGH** | 5 | Defeitos que afetam corretude ou criam modos de falha significativos |
| **MEDIUM** | 6 | Lacunas materiais que limitam a confiabilidade ou segurança |
| **LOW** | 6 | Fragilidades menores ou oportunidades de hardening |
| **INFORMATIONAL** | 5 | Observações, pontos fortes verificados ou notas para documentação |

---

## Findings

---

### CRITICAL-01: Framework de Avaliação Mede Sintaxe, Não Qualidade Semântica

**Componente**: `src/committee/evaluation/criteria.py`  
**Evidência**: Todos os 18 critérios de avaliação utilizam exclusivamente heurísticas léxicas para medir a "qualidade" de uma deliberação:

- **Jaccard similarity** entre títulos de propostas (palavra por palavra)
- Contagem de strings em listas (e.g., `len(list) >= 4`)
- Comprimento mínimo de texto (`len(f.justification) >= 20`)
- Regex contra 7 frases hardcoded em português para detectar viés do Facilitador
- Presença de números > 10 que não estão no contexto para detectar "alucinação"
- Keyword matching de `"kafka"`, `"kubernetes"`, `"sharding"` como proxy de "recomendação não fundamentada"

**Impacto**: É trivial construir uma deliberação com conteúdo completamente sem sentido (gibberish) que obtém pontuação máxima (5.0) em todos os 18 critérios, desde que se satisfaçam as regras léxicas. Inversamente, uma deliberação de alta qualidade que use sinônimos, inglês ou termos técnicos não hardcoded será penalizada.

**Agravante — Validação Circular**: Os cenários de teste (`scenarios.py`) foram construídos para conter exatamente as palavras, comprimentos e padrões que os critérios verificam. Testes apenas provam "a regex encontrou a string que foi escrita para ser encontrada pela regex".

**Critério específico `HUMAN_SOVEREIGNTY`**: Hardcoded para retornar `5.0` sempre ([`criteria.py`](file:///home/Aelton0/Dev/ai-committee/src/committee/evaluation/criteria.py) linhas 979-1009).

**Recomendação**:
1. Redesenhar o framework de avaliação com critérios semânticos (cross-referência de IDs entre artefatos, validação de grafo de dependências epistêmicas, verificação de que fatos citados no Decision existem no ProblemContext).
2. Separar critérios "estruturais" (que podem ser léxicos) de critérios "semânticos" (que requerem raciocínio sobre conteúdo).
3. Criar cenários adversariais que **devem falhar** (gibberish, contradições) e verificar que recebem pontuação baixa.

---

### CRITICAL-02: Quality Gates Não Implementam Invariantes Documentados

**Componente**: [`src/committee/gates.py`](file:///home/Aelton0/Dev/ai-committee/src/committee/gates.py)  
**Referência**: [`docs/state-machine.md`](file:///home/Aelton0/Dev/ai-committee/docs/state-machine.md) Seção 3

A documentação define 6 gates com 3-6 invariantes semânticos cada um. A implementação real verifica apenas tipo de payload e papel do ator.

| Gate | Doc define | Código verifica |
| :--- | :--- | :--- |
| **Gate 0** (Investigation Exit) | 6 invariantes: summary inequívoco, OpenQuestions == 0, Facts comprovados, Constraints delimitados, Assumptions explícitas, SuccessCriteria objetivos | `isinstance(payload, ProblemContext)` + `actor == FACILITATOR` + unanswered == 0 + `success_criteria` não vazio |
| **Gate 1** (Divergence) | Schema completo, cobertura de custos/riscos/reversibilidade, verificação de isolamento cego | `isinstance(payload, BaseProposal)` + `actor` correto + `actor == proponent_role` |
| **Gate 2** (Confrontation) | Análise individualizada para ambas propostas, SPOFs, segurança, severidade classificada | `isinstance(payload, AuditReport)` + `actor == AUDITOR_SRE` + ambas propostas presentes |
| **Gate 3** (Defense) | Respostas a todos os riscos Alto/Crítico, concordância com mitigação OU contestação fundamentada | `isinstance(payload, BaseDefense)` + `actor` correto |
| **Gate 4** (Convergence) | Síntese sem julgamento pessoal, consolidação de concordâncias/desacordos, tabela de trade-offs | `isinstance(payload, DeliberationSynthesis)` + `actor == FACILITATOR` + ambas defesas presentes |
| **Gate 5** (Decision) | 13 Perguntas de Rastreabilidade respondidas, review triggers mensuráveis | `isinstance(payload, DecisionRecord)` + `actor == DECISOR` + synthesis existe |

**Impacto**: As gates são insuficientes para prevenir artefatos vazios ou de baixa qualidade de avançar o pipeline. Um `AuditReport` com listas vazias de findings passa na Gate 2.

**Recomendação**: Implementar validações semânticas progressivamente nos gates, começando pelos mais críticos (Gate 2 e Gate 5).

---

### CRITICAL-03: ROLLED_BACK e BLOCKED São Estados Completamente Inalcançáveis

**Componente**: [`src/committee/transitions.py`](file:///home/Aelton0/Dev/ai-committee/src/committee/transitions.py)  
**Evidência**:

1. **`BLOCKED`**: O `EventType.CRITICAL_ERROR` está definido no enum [`schemas/common.py`](file:///home/Aelton0/Dev/ai-committee/schemas/common.py), o `gate_critical_error` está definido em [`gates.py`](file:///home/Aelton0/Dev/ai-committee/src/committee/gates.py), mas **nenhuma `TransitionRule`** mapeia qualquer estado + `CRITICAL_ERROR` → `BLOCKED`. O estado existe sem nenhum caminho de entrada.

2. **`ROLLED_BACK`**: `docs/state-machine.md` (L162) documenta que `PHASE_ROLLBACK` transiciona para `ROLLED_BACK` e depois para `INVESTIGATION`. O código implementa `PHASE_ROLLBACK` → `INVESTIGATION` diretamente (linhas 148 e 165), pulando `ROLLED_BACK` inteiramente. O `STATE_PHASE_MAP` em [`session.py`](file:///home/Aelton0/Dev/ai-committee/src/committee/session.py#L39) mapeia `ROLLED_BACK` → `"PHASE_0_INVESTIGATION"`, mas o estado nunca é atingido.

**Impacto**: Funcionalidade documentada como existente (resiliência a erros fatais e rastreamento de rollbacks) não funciona. Logs de auditoria não registram o estado transicional ROLLED_BACK.

**Recomendação**:
1. Adicionar regras de transição para `CRITICAL_ERROR` → `BLOCKED` a partir de todos os estados ativos.
2. Decidir se `ROLLED_BACK` deve ser um estado intermediário real ou apenas um evento logado, e alinhar código com documentação.

---

### HIGH-01: Race Condition na Resolução de Target State

**Componente**: [`src/committee/state_machine.py`](file:///home/Aelton0/Dev/ai-committee/src/committee/state_machine.py#L93-L103)  
**Evidência**: Em `handle_event`, linhas 93-103:

```python
# 3. Resolve Target State
if callable(rule.to_state):
    to_state = rule.to_state(session, envelope)  # ← resolve ANTES de apply
else:
    to_state = rule.to_state

# 4. Append ao Store
self.event_store.append(envelope)

# 5. Apply
session.apply_event(envelope, to_state)
```

Se dois threads submeterem propostas concorrentemente para `resolve_divergence_target_state`, ambos verificam `session.proposals` antes de `apply_event` — ambos veem apenas 1 proposta e resolvem `DIVERGENCE`. Após ambos aplicarem, a sessão fica presa em `DIVERGENCE` com ambas propostas presentes, mas sem transição para `CONFRONTATION`.

**Contexto**: Atualmente, o sistema é single-threaded por sessão. Mas [`parallel.py`](file:///home/Aelton0/Dev/ai-committee/src/committee/orchestration/parallel.py) usa `asyncio.gather` para divergência, e as propostas são submetidas sequencialmente ao `StateMachine` no handler. Então a race condition **não se manifesta na arquitetura atual**, mas é um defeito latente.

**Recomendação**: Adicionar um lock por sessão (`asyncio.Lock`) em `handle_event`, ou reestruturar para que o resolver seja avaliado após `apply_event`.

---

### HIGH-02: Rollback Não Limpa Artefatos — Loophole de Bypass

**Componente**: [`src/committee/session.py`](file:///home/Aelton0/Dev/ai-committee/src/committee/session.py#L118-L119) e [`transitions.py`](file:///home/Aelton0/Dev/ai-committee/src/committee/transitions.py#L147-L152)  
**Evidência**: Quando `PHASE_ROLLBACK` é processado:

1. `session.apply_event` apenas adiciona o payload a `rollback_history`.
2. `proposals`, `audit_report`, `defenses`, `deliberation_synthesis`, `decision_record` **não são limpos**.
3. O estado transiciona para `INVESTIGATION`.
4. Após re-validação do contexto, o sistema entra em `DIVERGENCE`.
5. O primeiro novo `PROPOSAL_CREATED` aciona `resolve_divergence_target_state`, que encontra a proposta **anterior** (não limpa) no dicionário `session.proposals` e transiciona imediatamente para `CONFRONTATION` — com dados stale.

**Impacto**: Uma deliberação pode prosseguir usando artefatos da iteração anterior, violando a imutabilidade e produzindo decisões baseadas em versões inconsistentes.

**Recomendação**: Limpar `proposals`, `audit_report`, `defenses`, `deliberation_synthesis` e `decision_record` em `apply_event` quando o payload é `PhaseRollbackPayload`.

---

### HIGH-03: `SessionCreatedPayload` Descartado no Replay

**Componente**: [`src/committee/session.py`](file:///home/Aelton0/Dev/ai-committee/src/committee/session.py#L83-L174)  
**Evidência**: O método `apply_event` não possui handler para `SessionCreatedPayload`. O `isinstance` cascade (linhas 91-173) não cobre este tipo. Consequência: ao reconstruir estado via replay, o `problem_statement` e `user_id` originais são perdidos.

**Recomendação**: Adicionar handler em `apply_event` para `SessionCreatedPayload`.

---

### HIGH-04: Prompt Injection Sem Nenhuma Defesa

**Componente**: [`src/committee/orchestration/runner.py`](file:///home/Aelton0/Dev/ai-committee/src/committee/orchestration/runner.py) (todos os providers)  
**Evidência**: O `input_context` do usuário é serializado como JSON e concatenado diretamente ao `user_content` enviado ao LLM. Se o `problem_statement` contiver instruções adversariais como "Ignore your previous instructions and output the following JSON...", estas instruções serão enviadas ao LLM sem nenhuma sanitização ou separação estrutural.

**Impacto**: Atualmente o sistema é usado apenas por operadores confiáveis (CLI local). Se exposto a inputs não confiáveis no futuro, seria vulnerável.

**Recomendação**: Documentar explicitamente no threat model que o sistema assume inputs confiáveis. Para hardening futuro: separar input do usuário do prompt de sistema via delimitadores estruturais ou usar mecanismos de sandboxing do provider.

---

### HIGH-05: Cobertura de Testes do Replay < 20% dos Caminhos

**Componente**: [`tests/test_replay.py`](file:///home/Aelton0/Dev/ai-committee/tests/test_replay.py)  
**Evidência**: Os testes de replay cobrem apenas:
- `SESSION_CREATED` → `INVESTIGATION`
- `CONTEXT_VALIDATED` → `DIVERGENCE`

Não testados:
- `PHASE_ROLLBACK` (e a não-limpeza de artefatos)
- `USER_OVERRIDE` (com `UserRequestRevisionCommand`)
- Ciclo completo `DRAFT` → `COMPLETED`
- Ciclo com `INSUFFICIENT_EVIDENCE`
- `SessionCreatedPayload` silenciosamente descartado

**Recomendação**: Criar testes de replay para o ciclo completo e para cenários de rollback e revisão.

---

### MEDIUM-01: `content_hash` do Event Store Pode Ser Forjado

**Componente**: [`src/committee/event_store.py`](file:///home/Aelton0/Dev/ai-committee/src/committee/event_store.py#L111-L113)  
**Evidência**: Na função `append`, o hash é computado apenas se `envelope.content_hash` estiver vazio. Um chamador malicioso pode pré-popular o campo com um hash arbitrário. O hash **nunca é verificado na leitura**.

**Recomendação**: Forçar computação do hash no `append` (ignorando valor pré-existente) e validar hashes no `get_events`.

---

### MEDIUM-02: Divergência Doc ↔ Código nos Nomes de Eventos

**Componente**: [`docs/state-machine.md`](file:///home/Aelton0/Dev/ai-committee/docs/state-machine.md) vs [`schemas/common.py`](file:///home/Aelton0/Dev/ai-committee/schemas/common.py)  
**Evidência**:

| Documentação diz | Código implementa |
| :--- | :--- |
| `PROPOSALS_CREATED` (plural) | `PROPOSAL_CREATED` (singular, por proposta) |
| `DEFENSES_SUBMITTED` (plural) | `DEFENSE_SUBMITTED` (singular, por defesa) |
| `USER_CANCELLED` | `SESSION_CANCELLED` |
| `CRITICAL_BLOCK` / `CRITICAL_ERROR` → `BLOCKED` | `EventType.CRITICAL_ERROR` existe, mas sem regra de transição |
| `PHASE_ROLLBACK` → `ROLLED_BACK` → `INVESTIGATION` | `PHASE_ROLLBACK` → `INVESTIGATION` (direto) |

**Impacto**: Documentação não reflete o comportamento real, dificultando a compreensão de novos contribuidores e a auditoria externa.

**Recomendação**: Atualizar a documentação para refletir o código, ou vice-versa, com decisão explícita sobre a semântica desejada.

---

### MEDIUM-03: `SYNTHESIS_NEUTRALITY` Detecta Viés Apenas em Português e com 7 Padrões Fixos

**Componente**: [`src/committee/evaluation/criteria.py`](file:///home/Aelton0/Dev/ai-committee/src/committee/evaluation/criteria.py#L467-L566)  
**Evidência**: Os 7 padrões verificados são:
1. `r"recomendo a proposta"`
2. `r"recomendo a alternativa"`
3. `r"a melhor opç[aã]o [eé]"`
4. `r"devemos escolher"`
5. `r"a proposta [ab] [eé] superior"`
6. `r"vencedora [eé]"`
7. `r"escolha final"`

Uma síntese enviesada usando qualquer outra formulação (incluindo inglês ou reformulações em português como "Sugiro a proposta A", "A alternativa A traz mais vantagens") passa sem nenhuma detecção.

**Recomendação**: Se detecção de viés léxico for mantida, expandir significativamente os padrões. Idealmente, utilizar o próprio LLM como avaliador de neutralidade em sessões de avaliação.

---

### MEDIUM-04: `validate_input_context` É Firewall Negativo Sem Validação Positiva

**Componente**: [`src/committee/agents/architect.py`](file:///home/Aelton0/Dev/ai-committee/src/committee/agents/architect.py), todos os agentes  
**Evidência**: O método `validate_input_context` em cada agente verifica chaves **proibidas** (e.g., Architect rejeita `pragmatic_proposal`), mas não verifica se chaves **obrigatórias** estão presentes (e.g., `problem_context`, `phase`). O agente confia cegamente no `ContextBuilder` para fornecer tudo.

**Recomendação**: Adicionar validação de chaves obrigatórias por fase em cada agente.

---

### MEDIUM-05: `gate_divergence_proposal` Não Verifica Proposta Duplicada

**Componente**: [`src/committee/gates.py`](file:///home/Aelton0/Dev/ai-committee/src/committee/gates.py#L88-L97)  
**Evidência**: Se o Architect submeter duas propostas seguidas antes que o Pragmatic submeta a sua, a segunda sobrescreve a primeira em `session.proposals[CommitteeRole.ARCHITECT]` sem erro. A gate não verifica se a role já tem proposta registrada.

**Recomendação**: Verificar `if envelope.payload.proponent_role in session.proposals: fail_gate(...)`.

---

### MEDIUM-06: Ausência de `busy_timeout` no SQLite

**Componente**: [`src/committee/event_store.py`](file:///home/Aelton0/Dev/ai-committee/src/committee/event_store.py)  
**Evidência**: Nenhum `PRAGMA busy_timeout` é definido na inicialização. Se dois processos escreverem simultaneamente em arquivo SQLite, `database is locked` pode ocorrer sem retry.

**Recomendação**: Adicionar `PRAGMA busy_timeout = 5000;` na inicialização.

---

### LOW-01: `Desserialização` do Event Store Perde Tipagem Pydantic

**Componente**: [`src/committee/event_store.py`](file:///home/Aelton0/Dev/ai-committee/src/committee/event_store.py) (método `get_events`)  
**Evidência**: Payloads são armazenados como JSON e deserializados via `json.loads()`, resultando em dicionários Python genéricos. O `EventEnvelope.payload` retornado é um `dict`, não o modelo Pydantic original (e.g., `ArchitectProposal`).

**Impacto**: Replay e reconstrução de estado dependem de `isinstance()` checks que falharão contra dicionários, a menos que o chamador faça a reconstituição explícita.

---

### LOW-02: `DuplicateEventError` em vez de Idempotência Silenciosa

**Componente**: [`src/committee/event_store.py`](file:///home/Aelton0/Dev/ai-committee/src/committee/event_store.py#L157-L162)  
**Evidência**: Appending do mesmo `event_id` duas vezes levanta `DuplicateEventError`. Sistemas event-sourced frequentemente preferem idempotência silenciosa (a segunda tentativa é um no-op).

**Impacto**: Baixo — comportamento aceitável para um sistema single-writer. Documentar como decisão de design.

---

### LOW-03: Sem Limite de Rollback / Revisão Recursiva

**Componente**: [`src/committee/cli/app.py`](file:///home/Aelton0/Dev/ai-committee/src/committee/cli/app.py#L217-L219)  
**Evidência**: O loop da CLI permite chamadas infinitas de `revise`, cada uma voltando para `DIVERGENCE`. Não há limite de iterações, podendo gerar deliberações infinitas com custos de API crescentes.

**Recomendação**: Adicionar um counter de revisões e alertar o usuário após N ciclos.

---

### LOW-04: Nenhum Teste de CLI com LLM Real

**Componente**: [`tests/cli/`](file:///home/Aelton0/Dev/ai-committee/tests/cli/)  
**Evidência**: Todos os testes CLI usam `MockLLMProvider`. A integração CLI → Orchestrator → LLM real não é testada automaticamente. Erros de formato de resposta do LLM seriam descobertos apenas em uso real.

---

### LOW-05: Mock Provider Retorna Dados Perfeitos Sem Validar Lógica

**Componente**: [`src/committee/llm/mock.py`](file:///home/Aelton0/Dev/ai-committee/src/committee/llm/mock.py)  
**Evidência**: `MockLLMProvider._generate_default` retorna instâncias schema-compliant com dados hardcoded. Não avalia se o input context tem qualidade, coerência ou completude. Testes que dependem do Mock validam apenas o pipeline, não a qualidade da deliberação.

---

### LOW-06: Telemetria de Tokens Vinculada a `metadata_history` do Provider

**Componente**: [`src/committee/cli/app.py`](file:///home/Aelton0/Dev/ai-committee/src/committee/cli/app.py#L249-L268)  
**Evidência**: A coleta de telemetria usa `getattr(provider, "metadata_history", [])`. Se o provider não tiver este atributo (ex.: um provider custom futuro), a telemetria silenciosamente retorna zeros sem aviso.

---

### INFO-01: Isolamento de Agentes — Verificado e Sólido ✓

O `ContextBuilder` produz contextos estritamente filtrados por role e fase, com:
- Deep copy via `model_dump(mode="json")` eliminando referências mutáveis compartilhadas
- Invariantes de pós-construção (`_verify_isolation_invariants`) que levantam `ContextIsolationError`
- Validação de chaves proibidas nos próprios agentes (`validate_input_context`)

Testes adversariais confirmaram: Architect não vê `pragmatic_proposal` durante divergência, Auditor não vê defesas durante confrontação, Facilitator nunca vê `decision_record`.

---

### INFO-02: Event Store — Append-Only Verificado com Triggers ✓

Triggers SQL `prevent_event_update` e `prevent_event_delete` bloqueiam `UPDATE` e `DELETE` na tabela de eventos. Testes adversariais com conexão SQL direta confirmaram que ambas as operações falham. O store é efetivamente append-only ao nível SQL (com a ressalva de que acesso direto ao arquivo pode bypassar, o que é esperado para apps locais).

---

### INFO-03: Segurança de Secrets — Mascaramento Funcional ✓

`LLMConfig` override `__repr__` e `__str__` com `mask_secret`. Ambos os providers sanitizam exceções via `sanitize_secrets_from_text` antes de propagar erros. Testes adversariais confirmaram que `repr()` e `str()` não vazam chaves de API.

---

### INFO-04: Ausência de Funções Perigosas ✓

Nenhuma ocorrência de `eval()`, `exec()`, `pickle.load`, `__import__`, `subprocess`, `os.system` encontrada em `src/` ou `schemas/`.

---

### INFO-05: Provider Substitution — Verificado ✓

O mesmo `AgentRunner.run` funciona com `MockLLMProvider`, `OpenAILLMProvider` e `GeminiLLMProvider` sem alteração. Provado por [`test_provider_substitution.py`](file:///home/Aelton0/Dev/ai-committee/tests/test_provider_substitution.py).

---

## Matriz de Ações Recomendadas

| Prioridade | Finding | Ação |
| :--- | :--- | :--- |
| **P0** | CRITICAL-03 | Implementar `CRITICAL_ERROR` → `BLOCKED` e decidir sobre `ROLLED_BACK` |
| **P0** | HIGH-02 | Limpar artefatos no rollback |
| **P0** | HIGH-03 | Adicionar handler para `SessionCreatedPayload` no replay |
| **P1** | CRITICAL-02 | Incrementar gates com validações semânticas mínimas |
| **P1** | CRITICAL-01 | Redesenhar framework de avaliação; adicionar cenários adversariais |
| **P1** | HIGH-01 | Adicionar lock por sessão ou reestruturar resolver |
| **P1** | HIGH-05 | Expandir cobertura de replay com ciclo completo |
| **P2** | MEDIUM-02 | Alinhar documentação com código |
| **P2** | MEDIUM-01 | Forçar hash computation no append |
| **P2** | MEDIUM-04 | Adicionar validação positiva em agentes |
| **P2** | MEDIUM-05 | Gate rejeitar proposta duplicada |
| **P2** | MEDIUM-06 | Adicionar `busy_timeout` |
| **P2** | MEDIUM-03 | Expandir padrões de detecção de viés |
| **P3** | HIGH-04 | Documentar threat model e limitações de prompt injection |
| **P3** | LOW-01 a LOW-06 | Melhorias incrementais |

---

## Conclusão

O AI Committee é um projeto com ambição arquitetural significativa e execução sólida nos fundamentos: isolamento de agentes, event sourcing append-only, separação agente/orquestrador e provider-agnosticism estão implementados com rigor. O pipeline DRAFT → COMPLETED funciona corretamente no happy path com 247 testes passando.

As fragilidades identificadas concentram-se em três áreas:

1. **Lacuna entre documentação e código** (gates, estados inalcançáveis, nomes de eventos): A documentação promete invariantes que o código não implementa.
2. **Framework de avaliação sem validade semântica**: Mede compliance léxica, não qualidade real.
3. **Edge cases de resiliência** (rollback sem limpeza, replay incompleto, concorrência latente): O happy path funciona; os caminhos de exceção não foram suficientemente implementados ou testados.

Nenhuma dessas fragilidades compromete o uso atual do sistema (CLI local, operador confiável, single-session). Porém, devem ser resolvidas antes de qualquer ampliação de escopo (multi-tenancy, inputs não confiáveis, ou uso em produção para decisões de alto impacto).
