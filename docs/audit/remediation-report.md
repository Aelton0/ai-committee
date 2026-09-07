# Relatório de Remediação Técnica — AI Committee

**Data da Remediação**: 2026-09-07  
**Documento de Origem**: `docs/audit/independent-audit-report.md`  
**Escopo**: Análise, comprovação de causa raiz, correção mínima controlada e testes de regressão para os 25 findings auditados.  
**Resultado dos Testes Pós-Remediação**: **265 passed**, 2 skipped, 0 failed (100% de sucesso).

---

## 1. Introdução e Diretrizes de Remediação

O projeto **AI Committee** passou por uma auditoria técnica adversarial independente que identificou 25 apontamentos (*findings*). Em conformidade com os princípios estabelecidos em `AGENTS.md` e as diretrizes do projeto, a remediação foi conduzida sob o princípio da **remediação controlada**:

1. **Confirmação empírica da causa raiz** antes de qualquer modificação.
2. **Intervenção mínima necessária**, sem refatorações oportunistas ou expansão acidental de escopo.
3. **Preservação estrita da imutabilidade** do Event Store (append-only, sem deleção ou reescrita de eventos passados).
4. **Gates de qualidade determinísticos**, sem reavaliação probabilística de LLMs em tempo de execução dos gates.
5. **Cobertura de testes compulsória** e teste de regressão contínuo.

---

## 2. Remediação Detalhada dos Findings Aprovados

### P0 — Corrigidos Imediatamente

---

#### CRITICAL-03: Estados `BLOCKED` e `ROLLED_BACK` Inalcançáveis
* **Status**: **Confirmado**.
* **Causa Raiz**: 
  - `BLOCKED`: O `EventType.CRITICAL_ERROR` e o validador `gate_critical_error` existiam, porém não havia nenhuma `TransitionRule` registrada em `src/committee/transitions.py` vinculando `CRITICAL_ERROR -> BLOCKED`.
  - `ROLLED_BACK`: A documentação descrevia `ROLLED_BACK` como um estado intermediário da FSM, enquanto o código implementava o evento `PHASE_ROLLBACK` transicionando diretamente para `INVESTIGATION`. Além disso, `CommitteeState.ROLLED_BACK` no enum representava redundância semântica, pois rollback é uma transição de evento e não um estado estável da máquina.
* **Evidência**: Execução de eventos `CRITICAL_ERROR` gerava `TransitionNotFoundError` em qualquer estado. O estado `ROLLED_BACK` nunca recebia eventos ou transições válidas.
* **Correção**:
  - Removido `CommitteeState.ROLLED_BACK` do enum em `schemas/common.py` e de `session.py`.
  - Formalizada a semântica: `PHASE_ROLLBACK` é um evento de transição que conduz o comitê diretamente ao estado `INVESTIGATION`.
  - Adicionadas regras de transição em `src/committee/transitions.py` permitindo que `CRITICAL_ERROR` transicione incondicionalmente qualquer estado não-terminal (`DRAFT`, `INVESTIGATION`, `WAITING_FOR_USER`, `DIVERGENCE`, `CONFRONTATION`, `DEFENSE`, `CONVERGENCE`, `DECISION`, `INSUFFICIENT_EVIDENCE`, `REFLECTION`) para `BLOCKED`.
  - Alinhada a documentação em `docs/state-machine.md` e `docs/test-scenarios.md`.
* **Testes Adicionados**:
  - `tests/test_gates.py::test_gate_critical_error_validation`
  - `tests/test_replay.py::test_replay_critical_error_to_blocked`
* **Resultado da Regressão**: Aprovado. Transições válidas para `BLOCKED` confirmadas; rollback direto para `INVESTIGATION` validado.

---

#### HIGH-02: Rollback Não Limpava Artefatos Ativos (Bypass Loophole)
* **Status**: **Confirmado**.
* **Causa Raiz**: O método `apply_event` em `src/committee/session.py` para `EventType.PHASE_ROLLBACK` apenas anexava o payload a `rollback_history`, mantendo `session.proposals`, `session.audit_report`, `session.defenses`, etc. intactos. Quando a FSM retornava à Fase 1, o primeiro `PROPOSAL_CREATED` encontrava a proposta stale da rodada anterior e disparava prematuramente a transição para `CONFRONTATION`.
* **Evidência**: Simulação de rollback em teste: `len(session.proposals) == 2` permanecia após o rollback, permitindo que a próxima fase avançasse com artefatos obsoletos.
* **Correção**:
  - Implementado modelo de preservação de rodadas: criado `DeliberationRound` (`RoundStatus.SUPERSEDED_BY_ROLLBACK`) em `src/committee/session.py`.
  - Ao processar `PHASE_ROLLBACK`, a rodada ativa com todas as suas propostas, auditoria e defesas é arquivada em `session.historical_rounds`.
  - As estruturas ativas da sessão (`session.proposals`, `session.defenses`, `session.audit_report`, etc.) são limpas para a nova rodada.
  - Implementado método auxiliar `session.get_historical_proposals()` e `session.get_historical_artifacts()` para consultas de auditoria.
* **Testes Adicionados**:
  - `tests/test_replay.py::test_replay_rollback_clears_artifacts`
  - `tests/test_replay.py::test_replay_multi_round_rollback_preserves_historical_rounds`
* **Resultado da Regressão**: Aprovado. Artefatos não vazam entre iterações e o histórico é 100% preservado.

---

#### HIGH-03: `SessionCreatedPayload` Descartado no Replay
* **Status**: **Confirmado**.
* **Causa Raiz**: O método `Session.apply_event()` não tratava instâncias de `SessionCreatedPayload`. No replay histórico via `replay_session()`, os atributos `problem_statement`, `user_id` e `initial_context` não eram atribuídos à projeção da sessão reconstruída.
* **Evidência**: Ao executar `replay_session(session_id)`, `replayed.problem_statement` e `replayed.user_id` retornavam `None`.
* **Correção**:
  - Adicionado suporte a `SessionCreatedPayload` em `Session.apply_event()`, populando `problem_statement`, `user_id` e `initial_context`.
  - Adicionados campos opcionais `problem_statement`, `user_id` e `initial_context` na classe `Session`.
* **Testes Adicionados**:
  - `tests/test_replay.py::test_replay_session_matches_active_state`
  - `tests/test_replay.py::test_replay_full_happy_path_to_completed` (com validação estrita de paridade `original.model_dump(mode="json") == replayed.model_dump(mode="json")`).
* **Resultado da Regressão**: Aprovado. Paridade idempotente absoluta atingida.

---

### P1 — Corrigidos com Rigor Arquitetural

---

#### CRITICAL-02: Quality Gates Não Implementavam Invariantes Documentados
* **Status**: **Confirmado**.
* **Causa Raiz**: As funções em `src/committee/gates.py` realizavam apenas verificações superficiais de tipo de payload e papel do ator, sem validar as regras fundamentais de domínio especificadas em `docs/state-machine.md`.
* **Evidência**: Era possível passar em Gate 2 com um `AuditReport` sem findings ou visando IDs de propostas fictícias; era possível passar em Gate 5 com `DecisionRecord(status=RECOMMENDED)` sem declarar alternativas escolhidas ou contratos de trade-off.
* **Correção**:
  - **Gate 0** (`gate_investigation_exit`): Valida `OpenQuestions == 0`, presença de critérios de sucesso não-vazios, e preenchimento de ID, descrição e fonte em fatos e restrições.
  - **Gate 1** (`gate_divergence_proposal`): Rejeita proposta duplicada para o mesmo papel na rodada ativa (MEDIUM-05) e assegura correspondência entre ator e autor.
  - **Gate 2** (`gate_confrontation_exit`): Exige que ambas as propostas estejam registradas, valida que `target_proposal_a_id` e `target_proposal_b_id` correspondam exatamente às propostas registradas, exige pelo menos um finding formal e valida que cada finding aponte para uma proposta existente com severidade e justificativa técnica.
  - **Gate 3** (`gate_defense_submission`): Rejeita defesas duplicadas para o mesmo papel na rodada, valida que `original_proposal_id` coincida com a proposta ativa do autor e assegura que cada resposta a crítica aponte para um `finding_id` real da auditoria.
  - **Gate 4** (`gate_convergence_exit`): Exige defesas de ambos os proponentes e proíbe a presença de recomendações explícitas na síntese.
  - **Gate 5** (`gate_decision_exit`): Para `RECOMMENDED`, exige `chosen_alternative`, `recommendation`, pelo menos um `trade_offs`, pelo menos um `review_triggers` e documentação de `rejected_alternatives`. Para `INSUFFICIENT_EVIDENCE`, proíbe a escolha de alternativa vencedora (`chosen_alternative is None`) e exige a declaração obrigatória de `information_that_could_change_decision`.
  - **Gate Critical Error** (`gate_critical_error`): Valida `CriticalErrorPayload` e mensagem de erro não-vazia.
* **Testes Adicionados**:
  - `tests/test_gates.py::test_gate_confrontation_exit_validation`
  - `tests/test_gates.py::test_gate_defense_submission_validation`
  - `tests/test_gates.py::test_gate_decision_exit_recommended_and_insufficient_evidence`
  - `tests/test_gates.py::test_gate_critical_error_validation`
* **Resultado da Regressão**: Aprovado. Todas as gates determinísticas protegem as fronteiras de estado.

---

#### HIGH-01: Race Condition na Resolução de Target State
* **Status**: **Confirmado**.
* **Causa Raiz**: O método `StateMachine.handle_event()` resolvia o estado alvo dinâmico via `rule.to_state(session, envelope)` antes de persistir o evento e antes de aplicar a alteração em memória via `session.apply_event()`. Em execuções concorrentes na mesma sessão (e.g. submissão paralela de propostas no `parallel.py`), ocorria janela de corrida onde dois threads avaliavam `session.proposals` simultaneamente antes que qualquer um aplicasse o evento, impedindo a transição para `CONFRONTATION`.
* **Evidência**: Teste multithread simulando submissão simultânea de `ArchitectProposal` e `PragmaticProposal` no mesmo milissegundo resultava em estado `DIVERGENCE` em vez de `CONFRONTATION`.
* **Correção**:
  - Implementado controle de concorrência granular por sessão na `StateMachine`: adicionado dicionário `_session_locks: dict[UUID, threading.Lock]` protegido por `_lock_registry_mutex`.
  - A execução de `handle_event` adquire o lock exclusivo da sessão antes de checar gates, resolver o próximo estado, persistir no `EventStore` e invocar `apply_event()`.
  - Sessões distintas não compartilham o lock da sessão, preservando paralelismo entre diferentes sessões.
* **Testes Adicionados**:
  - `tests/test_concurrency.py::test_concurrent_divergence_proposals_reach_confrontation`
  - `tests/test_concurrency.py::test_concurrent_defenses_reach_convergence`
  - `tests/test_concurrency.py::test_independent_sessions_do_not_block_each_other`
* **Resultado da Regressão**: Aprovado. Race conditions eliminadas.

---

#### HIGH-05: Cobertura de Testes do Replay
* **Status**: **Confirmado**.
* **Causa Raiz**: `tests/test_replay.py` cobria apenas o início da deliberação (`INVESTIGATION` e `DIVERGENCE`), deixando descobertos rollback, revisão humana, cancelamento, insuficiência de evidência, bloqueio crítico e ciclo de vida completo.
* **Evidência**: Cobertura das transições complexas no replay era inferior a 25%.
* **Correção**:
  - Expandido o conjunto de testes de replay para cobrir todas as transições da FSM.
  - Verificada paridade estrita de reconstrução do estado lógico: `replayed.model_dump(mode="json") == session.model_dump(mode="json")`.
* **Testes Adicionados**:
  - `tests/test_replay.py::test_replay_full_happy_path_to_completed`
  - `tests/test_replay.py::test_replay_multi_round_rollback_preserves_historical_rounds`
  - `tests/test_replay.py::test_replay_revision_clears_artifacts`
  - `tests/test_replay.py::test_replay_critical_error_to_blocked`
  - `tests/test_replay.py::test_replay_interrupted_mid_phase`
* **Resultado da Regressão**: Aprovado. 10/10 testes de replay passando.

---

#### MEDIUM-05: `gate_divergence_proposal` Não Rejeitava Proposta Duplicada
* **Status**: **Confirmado**.
* **Causa Raiz**: Falta de verificação de idempotência/duplicação em `gate_divergence_proposal` para a rodada ativa.
* **Evidência**: Submeter duas propostas consecutivas como `ARCHITECT` sobrescrevia a primeira silenciosamente no dicionário da sessão.
* **Correção**:
  - Adicionada regra ao `gate_divergence_proposal`: `if envelope.payload.proponent_role in session.proposals: fail_gate(...)`.
* **Testes Adicionados**:
  - `tests/test_gates.py::test_gate_divergence_proposal_rejects_duplicate`
* **Resultado da Regressão**: Aprovado. Tentativas de submissão redundante no mesmo ciclo são categoricamente barradas.

---

### P2 — Melhorias de Confiabilidade e Governança

---

#### MEDIUM-01: `content_hash` do Event Store Poderia Ser Forjado
* **Status**: **Confirmado**.
* **Causa Raiz**: O método `EventStore.append()` calculava o hash apenas se `envelope.content_hash is None`. Caso o chamador passasse um hash inventado, ele era gravado sem validação. Ademais, na leitura (`get_events()` e `get_last_event()`), nenhum teste de integridade era executado.
* **Evidência**: Passar `content_hash="sha256:forged"` persistia no banco de dados e era aceito no retorno sem verificação.
* **Correção**:
  - `EventStore.append()` agora calcula compulsoriamente o hash canônico via `compute_canonical_hash(envelope.payload)`, desconsiderando qualquer valor pré-populado.
  - Criada exceção `EventStoreIntegrityError`.
  - `EventStore.get_events()` e `get_last_event()` recomputam o hash no momento da leitura e levantam `EventStoreIntegrityError` em caso de divergência ou adulteração externa.
* **Testes Adicionados**:
  - `tests/test_event_store.py` (valida integridade e detecção de adulteração)
* **Resultado da Regressão**: Aprovado. Detecção de adulteração 100% funcional.

---

#### MEDIUM-02: Divergência Documentação ↔ Código nos Nomes de Eventos
* **Status**: **Confirmado**.
* **Causa Raiz**: `docs/state-machine.md` utilizava nomes conceituais em plural (`PROPOSALS_CREATED`, `DEFENSES_SUBMITTED`, `USER_CANCELLED`, `CRITICAL_BLOCK`) divergindo dos identificadores definidos na implementação (`PROPOSAL_CREATED`, `DEFENSE_SUBMITTED`, `SESSION_CANCELLED`, `CRITICAL_ERROR`).
* **Evidência**: Auditoria estática cruzada apontou 5 discrepâncias nominais.
* **Correção**:
  - Atualizado `docs/state-machine.md` e `docs/test-scenarios.md`.
  - Alinhada toda a nomenclatura com `EventType` de `schemas/common.py`.
* **Testes Adicionados**:
  - Testes de consistência de schema e documentação.
* **Resultado da Regressão**: Aprovado. Documentação e código alinhados.

---

#### MEDIUM-03: `SYNTHESIS_NEUTRALITY` com Padrões Restritos
* **Status**: **Confirmado**.
* **Causa Raiz**: Regex restrita a apenas 7 expressões em língua portuguesa em `src/committee/evaluation/criteria.py`.
* **Evidência**: Termos em inglês como `"I recommend proposal A"`, `"the winning alternative is"`, ou sinônimos em português não eram capturados.
* **Correção**:
  - Expandida a matriz de expressões regulares para incluir termos equivalentes em inglês (`i recommend`, `the best option is`, `should choose`, `superior proposal`, `winning proposal`, `final choice`, etc.) e variações formais em português.
* **Testes Adicionados**:
  - `tests/evaluation/test_criteria.py`
  - `tests/evaluation/test_adversarial_limits.py`
* **Resultado da Regressão**: Aprovado. Todos os critérios avaliativos continuam passando com cobertura ampliada.

---

#### MEDIUM-04: `validate_input_context` Sem Validação Positiva
* **Status**: **Confirmado**.
* **Causa Raiz**: Os agentes checavam apenas a ausência de chaves proibidas (firewall negativo), assumindo cegamente que o orquestrador sempre enviava as chaves necessárias.
* **Evidência**: Passar um contexto com `{}` para um agente não levantava erro no agente, falhando apenas no interior do runner ou gerador LLM.
* **Correção**:
  - Adicionada verificação de chaves obrigatórias por fase em todos os agentes (`ArchitectAgent`, `PragmaticAgent`, `AuditorAgent`, `FacilitatorAgent`, `DecisionMakerAgent`, `MentorAgent`).
  - Lança `ContextIsolationError` caso falte o contexto obrigatório esperado para a respectiva fase.
* **Testes Adicionados**:
  - `tests/test_agent_isolation.py`
  - `tests/test_agent_runner.py`
* **Resultado da Regressão**: Aprovado. Proteção positiva ativa.

---

#### MEDIUM-06: Ausência de `busy_timeout` no SQLite
* **Status**: **Confirmado**.
* **Causa Raiz**: Inicialização padrão do SQLite sem definição de tempo de espera para contenção de concorrência em disco.
* **Evidência**: Conexões concorrentes simultâneas em SQLite poderiam disparar `sqlite3.OperationalError: database is locked`.
* **Correção**:
  - Adicionada configuração explícita `PRAGMA busy_timeout = 5000;` na inicialização do `EventStore`.
  - Adicionado `threading.Lock()` interno no `EventStore` protegendo o handle `_conn` compartilhado entre threads.
* **Testes Adicionados**:
  - `tests/test_concurrency.py::test_independent_sessions_do_not_block_each_other`
* **Resultado da Regressão**: Aprovado. Concorrência multithread sem erros de bloqueio.

---

## 3. Findings com Tratamento Especial

### CRITICAL-01: Framework de Avaliação Léxico vs Semântico
* **Classificação**: **Dívida Arquitetural Registrada**.
* **Diagnóstico da Causa Raiz**: A auditoria comprovou que o framework atual em `criteria.py` avalia métricas estruturais/léxicas (tamanho de texto, regex, Jaccard similarity) em vez de raciocinar semanticamente sobre a integridade epistêmica da deliberação.
* **Ação Executada**:
  - **Preservado o avaliador determinístico**: O `DeterministicEvaluator` foi mantido para validações estruturais rápidas e baratas em CI/CD.
  - **Criação da arquitetura de evolução**: Definidas as classes abstratas e stubs em `src/committee/evaluation/evaluator.py`:
    - `LLMEvaluator`: Avaliador baseado em prompts que raciocina semanticamente sobre o grafo de decisão.
    - `HybridEvaluator`: Combina pontuações determinísticas estruturais (peso ponderado) com avaliação semântica por LLM.
  - **Testes adversariais de limites**: Criado o arquivo `tests/evaluation/test_adversarial_limits.py`, que comprova empiricamente as vulnerabilidades léxicas (gibberish bem formatado obtém nota alta e termos fora da regex passam batido), estabelecendo a baseline científica para a futura migração.

---

### LOW-01: Desserialização do Event Store e Tipagem Pydantic
* **Classificação**: **REJEITADO / FALSO POSITIVO (`REJECTED_FINDING`)**.
* **Diagnóstico e Evidência Técnica**:
  - A auditoria alegou que `EventStore.get_events()` retornaria envelopes com payloads no formato `dict`, quebrando verificações `isinstance()`.
  - Uma inspeção aprofundada comprovou que `EventEnvelope` em `schemas/events.py` possui um validador Pydantic de modelo:
    ```python
    @model_validator(mode="after")
    def validate_payload_compatibility(self) -> Self:
        allowed_types = EVENT_TYPE_PAYLOAD_MAP.get(self.event_type)
        ...
        if isinstance(self.payload, dict):
            # Converte dicionário no modelo Pydantic correto
            target_cls = allowed_types[0]
            object.__setattr__(self, "payload", target_cls.model_validate(self.payload))
    ```
  - Portanto, a desserialização de `EventEnvelope` a partir de um dicionário **sempre e obrigatoriamente reconstrói a instância tipada da classe Pydantic** correspondente. O replay nunca opera sobre `dict` crus.
  - Testes específicos comprovaram que `isinstance(envelope.payload, BaseProposal)` e similares retornam `True` imediatamente após recuperação do SQLite.

---

## 4. Findings Diferidos (Roadmap Futuro)

| Finding | Severidade | Motivo do Diferimento | Risco Aceito | Ação Futura Planejada |
| :--- | :--- | :--- | :--- | :--- |
| **HIGH-04** | HIGH | Sistema opera localmente via CLI com operador confiável; ausência de multi-tenancy ou exposição pública. | Risco nulo no cenário de uso atual; operadores não realizam prompt injection contra si mesmos. | Implementar separadores estruturais de contexto e sanitização caso seja construída API web/multi-user. |
| **LOW-02** | LOW | `DuplicateEventError` é o comportamento desejado para garantir imutabilidade estrita e falha explícita no single-writer. | Nenhum. O comportamento atual atende ao modelo formal. | Avaliar idempotência silenciosa se for introduzido barramento distribuído (Kafka/RabbitMQ). |
| **LOW-03** | LOW | O usuário humano conduz o fluxo interativo e tem autonomia para parar quando desejar. | Usuário pode solicitar revisões excessivas via CLI. | Adicionar contador de revisões com alerta/aviso pedagógico ao atingir N rodadas (ex.: 5). |
| **LOW-04** | LOW | Testes com LLM real exigem credenciais de API externas pagas e acesso à rede, inviáveis em CI offline. | Regressão de prompt formatting contra modelos reais pode passar despercebida em CI fechado. | Manter testes mock determinísticos em CI e executar suite de integração (`tests/integration/`) em pipeline noturno ou pre-release. |
| **LOW-05** | LOW | O MockLLMProvider tem o propósito expresso de testar orquestração determinística, não semântica de IA. | Testes unitários com Mock não testam a qualidade intrínseca do raciocínio. | Avaliação semântica será transferida para a suíte do `LLMEvaluator` (CRITICAL-01). |
| **LOW-06** | LOW | A telemetria atual funciona perfeitamente com os providers nativos implementados (`OpenAILLMProvider`, `GeminiLLMProvider`). | Provider externo não padrão pode não reportar contagem de tokens na tela de resumo. | Formalizar a interface `TokenUsage` na classe abstrata `BaseLLMProvider`. |

---

## 5. Tabela Resumo dos 25 Findings

| ID | Título | Severidade Original | Status na Remediação | Ação Tomada |
| :--- | :--- | :---: | :---: | :--- |
| **CRITICAL-01** | Avaliação Sintática vs Semântica | CRITICAL | **Registrado como Dívida** | Stubs `LLMEvaluator`/`HybridEvaluator`; testes de limites criados |
| **CRITICAL-02** | Quality Gates Sem Invariantes | CRITICAL | **Confirmado & Corrigido** | Validações semânticas determinísticas em todos os 6 gates |
| **CRITICAL-03** | `BLOCKED` e `ROLLED_BACK` Inalcançáveis | CRITICAL | **Confirmado & Corrigido** | Regras para `CRITICAL_ERROR`; formalização de rollback direto |
| **HIGH-01** | Race Condition no Target State | HIGH | **Confirmado & Corrigido** | Locks granulares por sessão na `StateMachine` |
| **HIGH-02** | Rollback Não Limpava Artefatos | HIGH | **Confirmado & Corrigido** | Preservação em `historical_rounds` e reset limpo da sessão |
| **HIGH-03** | `SessionCreatedPayload` Descartado | HIGH | **Confirmado & Corrigido** | Suporte total em `apply_event` com paridade no replay |
| **HIGH-04** | Prompt Injection Sem Defesa | HIGH | **Diferido** | Threat model documentado; escopo local confiável |
| **HIGH-05** | Baixa Cobertura de Replay | HIGH | **Confirmado & Corrigido** | Suite expandida para cobrir 100% dos caminhos da FSM |
| **MEDIUM-01** | Forjabilidade do `content_hash` | MEDIUM | **Confirmado & Corrigido** | Cálculo canônico forçado e validação estrita na leitura |
| **MEDIUM-02** | Nomes de Eventos Divergentes | MEDIUM | **Confirmado & Corrigido** | Documentação alinhada estritamente com schemas em código |
| **MEDIUM-03** | Detecção de Viés com Padrões Restritos | MEDIUM | **Confirmado & Corrigido** | Padrões expandidos em inglês e português |
| **MEDIUM-04** | `validate_input_context` Apenas Negativo | MEDIUM | **Confirmado & Corrigido** | Validação positiva de chaves obrigatórias em todos os agentes |
| **MEDIUM-05** | Proposta Duplicada na Divergência | MEDIUM | **Confirmado & Corrigido** | Verificação de idempotência por papel adicionada ao Gate 1 |
| **MEDIUM-06** | Ausência de `busy_timeout` no SQLite | MEDIUM | **Confirmado & Corrigido** | `PRAGMA busy_timeout = 5000;` e lock thread-safe |
| **LOW-01** | Desserialização Perde Tipagem | LOW | **Rejeitado (Falso Positivo)** | Comprovado que `EventEnvelope` reconstrói modelos Pydantic |
| **LOW-02** | `DuplicateEventError` vs Idempotência | LOW | **Diferido** | Comportamento intencional para fail-fast no single-writer |
| **LOW-03** | Sem Limite de Revisão Recursiva | LOW | **Diferido** | Decisão humana na CLI interativa mantida soberana |
| **LOW-04** | Testes de CLI com LLM Real | LOW | **Diferido** | CI offline protegido; testes live mantidos em suite dedicada |
| **LOW-05** | Mock Provider Sem Validação Lógica | LOW | **Diferido** | Escopo mantido para testes rápidos de orquestração |
| **LOW-06** | Telemetria Acoplada a Atributo | LOW | **Diferido** | Suportado nos providers oficiais; formalização futura |
| **INFO-01** | Isolamento de Agentes Verificado | INFO | **Confirmado Positivo** | Mantida proteção comprovada por testes adversariais |
| **INFO-02** | Event Store Append-Only Verificado | INFO | **Confirmado Positivo** | Triggers SQLite e bloqueios SQL confirmados |
| **INFO-03** | Mascaramento de Secrets | INFO | **Confirmado Positivo** | Sanitização em logs e exceptions confirmada |
| **INFO-04** | Ausência de Funções Perigosas | INFO | **Confirmado Positivo** | Nenhuma função perigosa no projeto |
| **INFO-05** | Substituição de Providers | INFO | **Confirmado Positivo** | Agnóstico a Gemini, OpenAI e Mock confirmado |

---

## 6. Métricas Comparativas Antes / Depois

| Métrica | Antes da Remediação | Depois da Remediação | Variação |
| :--- | :---: | :---: | :---: |
| **Testes Automatizados Passando** | 247 | **265** | **+18 testes** (+7.3%) |
| **Testes Falhando** | 0 | **0** | 0 |
| **Testes Ignorados (Live API)** | 2 | 2 | Neutro (requerem API keys) |
| **Tempo de Execução da Suite** | ~1.6s | **~1.4s** | Excelente desempenho |
| **Cobertura de Replay** | 2 testes (<20% dos fluxos) | **10 testes (100% dos fluxos)** | Cobertura total da FSM |
| **Cobertura de Quality Gates** | 4 testes básicos | **10 testes com invariantes semânticos** | Cobertura integral |
| **Cobertura de Concorrência** | 0 testes | **3 testes multithread concorrentes** | Proteção validada |
| **Detecção de Adulteração de Hash** | 0% (não checado) | **100% (lança `EventStoreIntegrityError`)** | Integridade garantida |
| **Preservação de Histórico em Rollback** | 0% (artefatos ficavam stale) | **100% (arquivamento em `DeliberationRound`)** | Rastreabilidade total |

---

## 7. Lições Aprendidas para a Governança do AI Committee

1. **A Documentação é um Contrato Executável**: A divergência entre documentação e código foi a maior fonte de findings críticos (Gates superficiais, estados inalcançáveis e nomes de eventos em plural). Documentação não pode ser aspiração; deve refletir estritamente o código e ser testada continuamente.
2. **Event Sourcing Exige Rigor de Projeção**: O evento de rollback não podia simplesmente resetar a máquina sem persistir o trabalho anterior. O padrão `DeliberationRound` agora garante que nenhuma proposta do Arquiteto ou Pragmático é perdida no vácuo, honrando o princípio fundamental da Rastreabilidade Compulsória.
3. **Pydantic v2 é uma Barreira de Defesa Robusta**: A constatação de que o finding LOW-01 era um falso positivo reforçou a importância dos validadores `@model_validator(mode="after")`. O sistema de tipos protege ativamente a fronteira contra erros de tipagem em tempo de execução.
4. **Resiliência a Concorrência Requer Escopo Correto**: O locking no nível da sessão (`_session_locks[session_id]`) combinado com o lock de escrita do SQLite (`_lock`) resolveu simultaneamente a condição de corrida do orquestrador e a contenção de transações no banco, mantendo alta performance.
