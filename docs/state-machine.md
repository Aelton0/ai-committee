# Máquina de Estados da Deliberação — AI Committee

Este documento formaliza a máquina de estados finitos (*Finite State Machine - FSM*) que governa o ciclo de vida de uma sessão do **AI Committee**. A execução de uma reunião é determinística, orientada a eventos e validada por portais de qualidade (*quality gates*).

---

## 1. Catálogo de Estados

A máquina de estados é composta por estados deliberativos ativos, estados de espera/interação humana e estados de exceção/terminais:

```
                            ┌──────────────┐
                            │    DRAFT     │
                            └──────┬───────┘
                                   │ SESSION_CREATED
                                   ▼
                       ┌───────────────────────┐
                       │     INVESTIGATION     │◄───────────────────┐
                       └───────────┬───────────┘                    │
                 QUESTION_RAISED   │   ▲                            │
                        ┌──────────┘   │ USER_RESPONDED             │
                        ▼              │                            │
             ┌───────────────────┐     │                            │
             │ WAITING_FOR_USER  ├─────┘                            │
             └──────────┬────────┘                                  │
                        │ CONTEXT_VALIDATED                         │
                        ▼                                           │
             ┌─────────────────────┐                                │
             │     DIVERGENCE      │                                │
             └──────────┬──────────┘                                │
                        │ PROPOSAL_CREATED (x2)                     │
                        ▼                                           │
             ┌─────────────────────┐       PHASE_ROLLBACK           │
             │    CONFRONTATION    ├────────────────────────────────┤
             └──────────┬──────────┘                                │
                        │ AUDIT_COMPLETED                           │
                        ▼                                           │
             ┌─────────────────────┐       PHASE_ROLLBACK           │
             │       DEFENSE       ├────────────────────────────────┤
             └──────────┬──────────┘                                │
                        │ DEFENSE_SUBMITTED (x2)                    │
                        ▼                                           │
             ┌─────────────────────┐                                │
             │     CONVERGENCE     │                                │
             └──────────┬──────────┘                                │
                        │ SYNTHESIS_CREATED                         │
                        ▼                                           │
             ┌─────────────────────┐                                │
             │      DECISION       ├──────────────┐                 │
             └──────────┬──────────┘              │                 │
                        │                         │                 │
      DECISION_RECORDED │                         │ DECISION_FAILED │
      (STATUS=RECOMMENDED)                        │ (INSUFFICIENT_  │
                        ▼                         │  EVIDENCE)      │
             ┌─────────────────────┐              │                 │
             │     REFLECTION      │              │                 │
             └──────────┬──────────┘              │                 │
                        │ LEARNING_REPORT_CREATED │                 │
                        ▼                         ▼                 │
             ┌─────────────────────┐    ┌────────────────────┐      │
             │      COMPLETED      │    │INSUFFICIENT_EVIDENCE│      │
             └─────────────────────┘    └────────────────────┘      │
                                                                    │
    [ Qualquer Estado Ativo ] ──► SESSION_CANCELLED ──► [ CANCELLED ]
    [ Qualquer Estado Ativo ] ──► CRITICAL_ERROR   ──► [ BLOCKED ]
```

### 1.1 Estados Ativos e Deliberativos
* `DRAFT`: Sessão recém-instanciada com o problema bruto submetido pelo usuário. Nenhum agente ativo ainda.
* `INVESTIGATION`: Facilitador em ação para dissecar o problema, extrair fatos, restrições, premissas, desconhecidos e critérios de sucesso.
* `WAITING_FOR_USER`: Execução pausada aguardando resposta humana a perguntas do Facilitador, validação de premissas ou decisão de continuidade.
* `DIVERGENCE`: Arquiteto e Pragmático gerando simultaneamente propostas técnicas independentes sob regime de isolamento estrito (*blind divergence*).
* `CONFRONTATION`: Auditor/SRE em ação inspecionando e atacando criticamente as propostas submetidas na Fase 1.
* `DEFENSE`: Arquiteto e Pragmático respondendo aos apontamentos da auditoria, refinando propostas e declarando divergências irredutíveis.
* `CONVERGENCE`: Facilitador organizando a síntese formal da deliberação (`DeliberationSynthesis`), mapeando consensos e dissensos sem emitir decisão.
* `DECISION`: Decisor formulando a recomendação do comitê com trade-offs, riscos e gatilhos de revisão, ou declarando insuficiência de evidência.
* `REFLECTION`: Mentor extraindo o dossiê pedagógico (`LearningReport`), conectando a prática aos fundamentos teóricos e apontando lacunas do usuário.
* `COMPLETED`: Estado terminal com sucesso; dossiê completo de decisão e mentoria disponível e imutável.

### 1.2 Estados de Exceção, Pausa e Terminais Alternativos
* `WAITING_FOR_USER`: Interrupção deliberada para interação com o usuário (perguntas abertas, aprovação de portão ou revisão).
* `BLOCKED`: Execução suspensa devido a erro de runtime crítico ou inconsistência insanável que impede deliberação (`CriticalErrorPayload`).
* `INSUFFICIENT_EVIDENCE`: Estado terminal em que o comitê formalmente atesta que os dados fornecidos não sustentam uma decisão técnica responsável.
* `CANCELLED`: Estado terminal acionado pelo usuário humano para abortar a sessão a qualquer momento.

---

## 2. Tabela Formal de Transições

| Estado Origem | Evento Disparador | Condição de Guarda (*Guard*) | Estado Destino | Efeitos Colaterais / Artefatos |
| :--- | :--- | :--- | :--- | :--- |
| `DRAFT` | `SESSION_CREATED` | Entrada do usuário não-nula | `INVESTIGATION` | Inicializa log append-only da sessão e contexto inicial. |
| `INVESTIGATION` | `QUESTION_RAISED` | Há informação crítica faltante (`OpenQuestions > 0`) | `WAITING_FOR_USER` | Notifica usuário com lista de perguntas. |
| `WAITING_FOR_USER` | `USER_RESPONDED` | Todas as perguntas obrigatórias foram respondidas | `INVESTIGATION` | Incorpora respostas ao rascunho de contexto. |
| `INVESTIGATION` | `CONTEXT_VALIDATED` | Fatos, restrições e premissas separados; `OpenQuestions == 0` | `DIVERGENCE` | Congela `ProblemContext` v1 (imutável). |
| `DIVERGENCE` | `PROPOSAL_CREATED` | Proposta válida submetida por Arquiteto ou Pragmático | `DIVERGENCE` (se 1ª) / `CONFRONTATION` (quando ambas registradas) | Registra `ArchitectProposal` e `PragmaticProposal`. Rejeita duplicata para mesmo papel na rodada. |
| `CONFRONTATION` | `AUDIT_COMPLETED` | Críticas estruturadas para ambas as propostas geradas | `DEFENSE` | Registra `AuditReport` v1 cobrindo ambas as propostas. |
| `CONFRONTATION` ou `DEFENSE` | `PHASE_ROLLBACK` | Auditor detecta premissa falsa basilar ou desconhecido bloqueante | `INVESTIGATION` | Arquiva rodada ativa em `historical_rounds` (`SUPERSEDED_BY_ROLLBACK`); limpa artefatos ativos da rodada. |
| `DEFENSE` | `DEFENSE_SUBMITTED` | Proponente respondeu aos apontamentos do Auditor | `DEFENSE` (se 1ª) / `CONVERGENCE` (quando ambas registradas) | Registra `ArchitectDefense` e `PragmaticDefense`. Valida referências a achados do audit report. |
| `CONVERGENCE` | `SYNTHESIS_CREATED` | Mapeamento neutro de consensos, divergências e trade-offs concluído | `DECISION` | Registra `DeliberationSynthesis` v1. |
| `DECISION` | `DECISION_RECORDED` | Recomendação técnica viável formulada com trade-offs e gatilhos | `REFLECTION` | Registra `DecisionRecord` (Status: `RECOMMENDED`). |
| `DECISION` | `DECISION_FAILED` | Evidências e premissas insuficientes para sustentar escolha | `INSUFFICIENT_EVIDENCE` | Registra `DecisionRecord` (Status: `INSUFFICIENT_EVIDENCE`). |
| `REFLECTION` | `LEARNING_REPORT_CREATED` | Conceitos, lacunas e guia de estudo mapeados | `COMPLETED` | Registra `LearningReport` v1; fecha sessão com sucesso. |
| *Qualquer Estado Não-Terminal* | `SESSION_CANCELLED` / `USER_OVERRIDE` | Usuário solicita abortamento explícito da sessão (`UserAbortCommand`) | `CANCELLED` | Registra motivo do cancelamento e preserva log histórico. |
| *Qualquer Estado Não-Terminal* | `CRITICAL_ERROR` | Erro não-recuperável de execução ou violação estrutural | `BLOCKED` | Registra diagnóstico de falha (`CriticalErrorPayload`). |

---

## 3. Portais de Qualidade (*Quality Gates*)

Nenhuma transição de fase ocorre automaticamente sem a validação do respectivo portal de qualidade:

### Gate 0: Saída de `INVESTIGATION` $\rightarrow$ `DIVERGENCE`
1. O campo `ProblemContext.problem` expressa o objetivo técnico e de negócio de forma inequívoca.
2. Não há itens não respondidos na lista `open_questions`.
3. Todo item na lista `facts` possui identificador, descrição e fonte delimitada.
4. Todo item na lista `constraints` possui identificador e descrição delimitada.
5. Todo item na lista `assumptions` está explicitado como premissa sujeita a risco.
6. A lista `success_criteria` possui pelo menos uma métrica ou condição objetiva não-vazia.

### Gate 1: Saída de `DIVERGENCE` $\rightarrow$ `CONFRONTATION`
1. Tanto `ArchitectProposal` quanto `PragmaticProposal` estão completas no schema exigido.
2. O ator do envelope corresponde estritamente ao `proponent_role`.
3. Não é permitida duplicidade de proposta para o mesmo papel na rodada ativa.
4. Não houve vazamento de contexto entre as propostas durante a geração (verificação de isolamento cego).

### Gate 2: Saída de `CONFRONTATION` $\rightarrow$ `DEFENSE`
1. O `AuditReport` contém análises específicas e individualizadas referenciando os IDs exatos de ambas as propostas registradas.
2. Contém pelo menos um achado formal (`findings_proposal_a` ou `findings_proposal_b`), com severidade e justificativa técnica.
3. Não referencia propostas inexistentes ou de outras sessões.

### Gate 3: Saída de `DEFENSE` $\rightarrow$ `CONVERGENCE`
1. O Arquiteto e o Pragmático responderam através de defesas estruturadas (`ArchitectDefense` e `PragmaticDefense`).
2. Cada resposta de crítica referencia um identificador válido de achado presente no `AuditReport`.
3. O `original_proposal_id` confere exatamente com a proposta ativa do proponente.
4. Não é permitida duplicidade de defesa para o mesmo papel na rodada ativa.

### Gate 4: Saída de `CONVERGENCE` $\rightarrow$ `DECISION`
1. A `DeliberationSynthesis` não expressa julgamento de preferência pessoal do Facilitador (neutra).
2. Consolida com clareza os pontos de concordância e os pontos de desacordo irredutíveis.
3. Mapeia a tabela comparativa de trade-offs de ambas as abordagens.

### Gate 5: Saída de `DECISION` $\rightarrow$ `REFLECTION` ou `INSUFFICIENT_EVIDENCE`
1. O `DecisionRecord` quando `RECOMMENDED` obrigatoriamente declara `chosen_alternative`, `recommendation`, pelo menos um contrato de trade-off (`trade_offs`), pelo menos um gatilho de revisão (`review_triggers`) e as alternativas rejeitadas (`rejected_alternatives`).
2. Quando `INSUFFICIENT_EVIDENCE`, proíbe a declaração de alternativa vencedora (`chosen_alternative is None`) e exige a declaração explícita de `information_that_could_change_decision`.

### Gate 6: Saída de `REFLECTION` $\rightarrow$ `COMPLETED`
1. O `LearningReport` identifica os conceitos de computação/engenharia subjacentes ao problema.
2. Fornece conexões pedagógicas entre a teoria e a decisão tomada.
3. Fornece recomendações qualificadas de estudo e perguntas para reflexão do usuário.

---

## 4. Protocolo de Rollback de Fases

Quando uma inconsistência basilar ou premissa falsa for identificada em fases posteriores, o sistema executa um **Rollback Controlado**:

1. **Gatilho de Rollback**:
   - Durante a Fase 2 (`CONFRONTATION`) ou Fase 3 (`DEFENSE`), o Auditor (ou comitê) constata que uma premissa fundamental aceita na Fase 0 é categoricamente falsa ou inviável, invalidando as propostas.
2. **Execução do Rollback**:
   - A máquina de estados processa o evento `PHASE_ROLLBACK`.
   - O estado atual transiciona diretamente para `INVESTIGATION`, gravando uma entrada imutável no log de auditoria.
   - O estado `ROLLED_BACK` não existe como estado estável da FSM: o rollback é a **transição de evento** que restaura o ciclo deliberativo em `INVESTIGATION`.
3. **Preservação Compulsória de Artefatos**:
   - Os artefatos gerados nas fases retrocedidas (`proposals`, `audit_report`, `defenses`) **jamais são destruídos**.
   - Eles são arquivados em `session.historical_rounds` como uma `DeliberationRound` com status `SUPERSEDED_BY_ROLLBACK` e carimbo temporal (`archived_at`), preservando a linhagem causal completa.
   - As estruturas ativas da rodada corrente são reinicializadas para permitir a formulação de novas propostas limpas.

---

## 5. Pontos de Intervenção Humana (*Human-in-the-Loop*)

O usuário humano possui autoridade para intervir nos seguintes pontos:
* **Interação Ordinária**: Responder às dúvidas na Fase 0 (`WAITING_FOR_USER`).
* **Contestação de Premissas**: O usuário pode rejeitar uma premissa formulada pelo Facilitador (`UserContestAssumptionCommand`).
* **Solicitação de Revisão / Nova Rodada**: Após a Fase 5 (`DECISION`, `INSUFFICIENT_EVIDENCE`, `REFLECTION` ou `COMPLETED`), o usuário pode rejeitar a recomendação do Decisor (`UserRequestRevisionCommand`). A rodada atual é arquivada em `historical_rounds` como `SUPERSEDED_BY_REVISION` e a FSM retorna a `DIVERGENCE`.
* **Encerramento Compulsório**: O usuário pode acionar cancelamento formal a qualquer momento (`SESSION_CANCELLED` ou `UserAbortCommand`), congelando a sessão com status `CANCELLED`.
