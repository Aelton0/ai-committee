# Arquitetura de Agentes e Orquestração — AI Committee

Este documento detalha o design técnico, a organização de componentes, as garantias de isolamento cognitivo e a dinâmica de orquestração da camada de agentes do **AI Committee**.

---

## 1. Visão Geral da Arquitetura

A camada de agentes e orquestração operacionaliza o protocolo dialético formalizando a interação entre agentes especializados e a autoridade central do sistema: a **State Machine** determinística e o **Event Store** *append-only*.

Nenhum agente e nenhum runner possui acesso de escrita direto ao Event Store ou à State Machine. O fluxo é estritamente unidirecional e orientado a artefatos tipados.

```text
┌──────────────┐     Filtered Context     ┌────────────────────────┐
│              │ ───────────────────────> │                        │
│ Context      │                          │ Specialized Agent      │
│ Builder      │                          │ (Prompt + Output Model)│
│              │                          └──────────┬─────────────┘
└──────────────┘                                     │ Calls LLM
                                                     ▼
┌──────────────────┐   Validated Artifact  ┌────────────────────────┐
│ State Machine    │ <──────────────────── │ AgentRunner            │
│ (Gates & Table)  │   (via Orchestrator)  │ (LLMProvider + Retry)  │
└────────┬─────────┘                       └────────────────────────┘
         │
         ▼ Appends atomically
┌──────────────────┐
│ Event Store      │
│ (SQLite / WAL)   │
└──────────────────┘
```

---

## 2. Componentes Fundamentais

### 2.1. BaseAgent e Especializações (`src/committee/agents/`)
Cada agente herda de `BaseAgent` (`base.py`) e encapsula:
* **`role`**: Identificador formal do papel (`CommitteeRole`).
* **`system_prompt`**: Prompt declarativo carregado de `agents/{slug}.md`.
* **`output_schema`**: Classe Pydantic correspondente ao artefato canônico produzido.
* **`validate_input_context(context)`**: Validação de segurança defensiva em nível de código para barrar vazamento de informações proibidas antes de chamar o modelo.

Agentes especializados implementados:
1. **`ArchitectAgent`**: Foco em integridade estrutural, desacoplamento e longevidade (`ArchitectProposal` e `ArchitectDefense`).
2. **`PragmaticAgent`**: Foco em time-to-value, KISS e simplicidade operacional (`PragmaticProposal` e `PragmaticDefense`).
3. **`AuditorAgent`**: Crítica adversarial rigorosa, SPOFs e detecção de over/underengineering (`AuditReport`).
4. **`FacilitatorAgent`**: Síntese imparcial dos debates sem emitir recomendações (`DeliberationSynthesis` ou `ProblemContext`).
5. **`DecisionMakerAgent`**: Balanço de trade-offs, riscos aceitos e recomendação ou `INSUFFICIENT_EVIDENCE` (`DecisionRecord`).
6. **`MentorAgent`**: Roteiro de estudos, lacunas cognitivas observadas e fundamentos de engenharia (`LearningReport`).

### 2.2. Abstração LLM Provider (`src/committee/llm/`)
* **`LLMProvider` (`provider.py`)**: Protocolo assíncrono mínimo:
  ```python
  class LLMProvider(Protocol):
      async def generate(
          self,
          *,
          system_prompt: str,
          input_context: dict[str, Any],
          output_schema: type[BaseModel],
      ) -> BaseModel: ...
  ```
  O provider retorna instâncias validadas do Pydantic diretamente, eliminando parsers frágeis baseados em expressões regulares.
* **`MockLLMProvider` (`mock.py`)**: Implementação determinística completa que emula o Comitê sem chamadas externas, com suporte a injeção de falhas programadas e geradores customizados para testes de integração.

### 2.3. Agent Runner (`src/committee/orchestration/runner.py`)
Componente *stateless* encarregado da execução:
1. Valida o contexto com `agent.validate_input_context(input_context)`.
2. Invoca o `LLMProvider`.
3. Valida a conformidade estrita com o `output_schema`.
4. Aplica política de **retentativas com limite** (`max_retries`).
5. Se as tentativas se esgotarem, levanta `AgentExecutionFailed`, abortando o passo sem persistir dados inválidos.

### 2.4. Context Builder (`src/committee/orchestration/context_builder.py`)
Componente responsável por construir a visão de contexto higienizada para cada papel e fase, em estrita observância a `docs/context-visibility.md`.
* Aplica o princípio da necessidade de conhecimento (*Need-to-Know*).
* Executa asserções pós-construção (`_verify_isolation_invariants`), impedindo que campos proibidos vazem acidentalmente.

### 2.5. Committee Orchestrator (`src/committee/orchestration/orchestrator.py`)
Orquestrador central que conecta:
* `StateMachine`
* `EventStore`
* `ContextBuilder`
* `AgentRunner`

O Orchestrator avança a deliberação passo a passo (`step()` e `run_until_pause()`), convertendo artefatos gerados em `EventEnvelope` e submetendo-os à State Machine.

---

## 3. Isolamento Cognitivo e Blind Divergence

O isolamento é assegurado em **duas camadas independentes** (Defesa em Profundidade):
1. **Camada 1 (ContextBuilder)**: Filtra os dados da sessão antes de gerar o payload de entrada.
2. **Camada 2 (Agent.validate_input_context)**: O próprio agente inspeciona o dicionário recebido e lança `ContextIsolationError` caso detecte dados não autorizados, antes mesmo de enviar o prompt ao LLM.

### Regras de Isolamento por Fase:
* **Fase 1 (Divergência Cega)**:
  - O Arquiteto recebe apenas `ProblemContext`. É terminantemente proibido conter dados da proposta do Pragmático.
  - O Pragmático recebe apenas `ProblemContext`. É terminantemente proibido conter dados da proposta do Arquiteto.
* **Fase 2 (Confronto / Auditoria)**:
  - O Auditor recebe `ProblemContext` e ambas as propostas.
  - O Auditor **NÃO recebe defesas** de nenhum proponente (as defesas só são elaboradas após o relatório de auditoria ser concluído).
* **Fase 3 (Defesa)**:
  - O Arquiteto recebe sua proposta e o `AuditReport`. NÃO recebe a defesa do Pragmático.
  - O Pragmático recebe sua proposta e o `AuditReport`. NÃO recebe a defesa do Arquiteto.
* **Fase 4 (Convergência / Neutralidade do Facilitador)**:
  - O Facilitador recebe os artefatos de debate anteriores.
  - O Facilitador **NUNCA recebe `DecisionRecord`** e seu schema de saída (`DeliberationSynthesis`) é proibido de emitir vereditos ou recomendações de solução.

---

## 4. Execução Concorrente (Parallel Execution)

Para viabilizar divergência cega genuína e evitar ancoragem temporal, os proponentes são executados concorrentemente via `asyncio.gather`:

```python
# Em src/committee/orchestration/parallel.py
async def run_divergence_parallel(...) -> tuple[ArchitectProposal, PragmaticProposal]:
    # 1. Os contextos são pré-construídos de forma completamente independente
    context_architect = context_builder.build_context(session, CommitteeRole.ARCHITECT, phase="PHASE_1_DIVERGENCE")
    context_pragmatic = context_builder.build_context(session, CommitteeRole.PRAGMATIST, phase="PHASE_1_DIVERGENCE")

    # 2. Execução concorrente
    return await asyncio.gather(
        runner.run(architect_agent, context_architect),
        runner.run(pragmatic_agent, context_pragmatic),
    )
```

Nenhum agente tem acesso ao resultado provisório do outro durante o processamento.

---

## 5. Tolerância a Falhas e Política de Retry

1. **Retentativas**: Se o LLM falhar ou emitir um payload que viole o schema Pydantic, o `AgentRunner` tenta novamente até `max_retries` vezes.
2. **Exaustão de Tentativas**: Se todas as tentativas falharem, é levantada a exceção `AgentExecutionFailed`.
3. **Não-Corrupção**: Como o Runner e o Agent não tocam no Event Store, uma falha de agente **não produz eventos espúrios** no histórico. A sessão permanece em seu estado original íntegro.

---

## 6. Fluxo de Artefatos e Relação com a State Machine

A **State Machine é a autoridade absoluta** da deliberação. O Orchestrator não decide se uma transição é válida nem avalia os Quality Gates diretamente:

```text
[Agent execution] 
       │ 
       ▼ Produces
[Artifact (Pydantic)]
       │
       ▼ Wrapped by Orchestrator
[EventEnvelope(actor, artifact_id, payload, ...)]
       │
       ▼ Submitted to
[StateMachine.handle_event(session, envelope)]
       │
       ├─► 1. Check valid transition rule in transitions table
       ├─► 2. Evaluate Quality Gate (e.g. GateDivergenceProposal)
       ├─► 3. Append event atomically to EventStore (WAL trigger protected)
       └─► 4. Apply mutation to in-memory Session projection
```

Se o Quality Gate falhar ou a transição for ilegal, a State Machine rejeita o evento com `QualityGateFailedError` ou `InvalidTransitionError`, impedindo a gravação no banco de dados.

---

## 7. Intervenção Humana (Human-in-the-Loop)

1. **Pausa Obrigatória (`WAITING_FOR_USER`)**: Quando o Facilitador detecta perguntas abertas não resolvidas na investigação, emite `QUESTION_RAISED`. O Orchestrator interrompe imediatamente o loop de processamento autônomo.
2. **Retomada**: A sessão só avança quando o usuário envia sua resposta através de `orchestrator.user_respond(session, question_id, answer)`, que submete o evento `USER_RESPONDED` e retorna o estado para `INVESTIGATION`.
3. **Intervenções Explícitas (`user_override`)**: Comandos humanos como `UserAbortCommand`, `UserRequestRevisionCommand` ou `UserContestAssumptionCommand` são submetidos como eventos auditáveis e alteram o estado da sessão de acordo com a tabela de transições.

---

## 8. Garantia de Rastreabilidade e Replay

Toda deliberação finalizada em `COMPLETED` pode ser reconstruída do zero através de:

```python
replayed_session = replay_session(session_id, event_store)
```

A reprodução reexecuta todas as transições e gates a partir do log imutável de eventos, garantindo paridade de 100% com o estado final ativo.
