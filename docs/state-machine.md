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
                        │ PROPOSALS_CREATED                         │
                        ▼                                           │
             ┌─────────────────────┐       PHASE_ROLLBACK           │
             │    CONFRONTATION    ├────────────────────────────────┤
             └──────────┬──────────┘                                │
                        │ AUDIT_COMPLETED                           │
                        ▼                                           │
             ┌─────────────────────┐                                │
             │       DEFENSE       │                                │
             └──────────┬──────────┘                                │
                        │ DEFENSES_SUBMITTED                        │
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
    [ Qualquer Estado Ativo ] ──► CRITICAL_BLOCK   ──► [ BLOCKED ]
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
* `ROLLED_BACK`: Estado transicional que registra a regressão controlada de uma fase adiantada para uma anterior (ex.: retorno à `INVESTIGATION` a partir de `CONFRONTATION`).
* `BLOCKED`: Execução suspensa devido a violação insolúvel de restrição ou inconsistência lógica insanável que exige intervenção externa.
* `INSUFFICIENT_EVIDENCE`: Estado terminal em que o comitê formalmente atesta que os dados fornecidos não sustentam uma decisão técnica responsável.
* `CANCELLED`: Estado terminal acionado pelo usuário humano para abortar a sessão a qualquer momento.

---

## 2. Tabela Formal de Transições

| Estado Origem | Evento Disparador | Condição de Guarda (*Guard*) | Estado Destino | Efeitos Colaterais / Artefatos |
| :--- | :--- | :--- | :--- | :--- |
| `DRAFT` | `SESSION_CREATED` | Entrada do usuário não-nula | `INVESTIGATION` | Inicializa log append-only da sessão. |
| `INVESTIGATION` | `QUESTION_RAISED` | Há informação crítica faltante (`OpenQuestions > 0`) | `WAITING_FOR_USER` | Notifica usuário com lista de perguntas. |
| `WAITING_FOR_USER` | `USER_RESPONDED` | Todas as perguntas obrigatórias foram respondidas | `INVESTIGATION` | Incorpora respostas ao rascunho de contexto. |
| `INVESTIGATION` | `CONTEXT_VALIDATED` | Fatos, restrições e premissas separados; `OpenQuestions == 0` | `DIVERGENCE` | Congela `ProblemContext` v1 (imutável). |
| `DIVERGENCE` | `PROPOSALS_CREATED` | Ambas as propostas (Arquiteto e Pragmático) emitidas e completas | `CONFRONTATION` | Registra `ArchitectProposal` v1 e `PragmaticProposal` v1. |
| `CONFRONTATION` | `AUDIT_COMPLETED` | Críticas estruturadas para ambas as propostas geradas | `DEFENSE` | Registra `AuditReport` v1. |
| `CONFRONTATION` | `PHASE_ROLLBACK` | Auditor detecta premissa falsa basilar ou desconhecido bloqueante | `INVESTIGATION` | Registra motivo do rollback; notifica usuário. |
| `DEFENSE` | `DEFENSES_SUBMITTED` | Proponentes responderam aos apontamentos do Auditor | `CONVERGENCE` | Registra `ArchitectDefense` e `PragmaticDefense`. |
| `CONVERGENCE` | `SYNTHESIS_CREATED` | Mapeamento de consensos, divergências e trade-offs concluído | `DECISION` | Registra `DeliberationSynthesis` v1. |
| `DECISION` | `DECISION_RECORDED` | Recomendação técnica viável formulada com trade-offs e gatilhos | `REFLECTION` | Registra `DecisionRecord` (Status: `RECOMMENDED`). |
| `DECISION` | `DECISION_FAILED` | Evidências e premissas insuficientes para sustentar escolha | `INSUFFICIENT_EVIDENCE` | Registra `DecisionRecord` (Status: `INSUFFICIENT_EVIDENCE`). |
| `REFLECTION` | `LEARNING_REPORT_CREATED` | Conceitos, lacunas e guia de estudo mapeados | `COMPLETED` | Registra `LearningReport` v1; fecha sessão. |
| *Qualquer Estado* | `USER_CANCELLED` | Usuário solicita abortamento explícito da sessão | `CANCELLED` | Registra motivo do cancelamento e preserva log. |
| *Qualquer Estado* | `CRITICAL_ERROR` | Erro não-recuperável de execução ou violação estrutural | `BLOCKED` | Registra stacktrace e diagnóstico de falha. |

---

## 3. Portais de Qualidade (*Quality Gates*)

Nenhuma transição de fase ocorre automaticamente sem a validação do respectivo portal de qualidade:

### Gate 0: Saída de `INVESTIGATION` $\rightarrow$ `DIVERGENCE`
1. O campo `ProblemContext.summary` expressa o objetivo técnico e de negócio de forma inequívoca.
2. Não há itens não respondidos na lista `OpenQuestions`.
3. Todo item na lista `Facts` é comprovado ou validado pelo usuário.
4. Todo item na lista `Constraints` possui impacto delimitado.
5. Todo item na lista `Assumptions` está explicitado como premissa sujeita a risco.
6. A lista `SuccessCriteria` possui pelo menos uma métrica ou condição objetiva de sucesso.

### Gate 1: Saída de `DIVERGENCE` $\rightarrow$ `CONFRONTATION`
1. Tanto `ArchitectProposal` quanto `PragmaticProposal` estão completas no schema exigido.
2. Ambas as propostas cobrem obrigatoriamente: solução, justificativa, custos, riscos, complexidade operacional, reversibilidade, premissas assumidas e condições de obsolescência.
3. Não houve vazamento de contexto entre as propostas durante a geração (verificação de isolamento cego).

### Gate 2: Saída de `CONFRONTATION` $\rightarrow$ `DEFENSE`
1. O `AuditReport` contém análises específicas e individualizadas para ambas as propostas.
2. Contém avaliação de pontos únicos de falha (SPOFs), superfícies de segurança, riscos operacionais e custos ocultos.
3. Classifica a gravidade de cada risco apontado (Baixo, Médio, Alto, Crítico).

### Gate 3: Saída de `DEFENSE` $\rightarrow$ `CONVERGENCE`
1. O Arquiteto e o Pragmático responderam explicitamente a todos os riscos classificados como Alto ou Crítico no `AuditReport`.
2. Para cada apontamento, há concordância expressa com mitigação OU contestação técnica fundamentada.
3. As propostas originais (v1) permaneceram intactas; refinamentos foram adicionados formalmente.

### Gate 4: Saída de `CONVERGENCE` $\rightarrow$ `DECISION`
1. A `DeliberationSynthesis` não expressa julgamento de preferência pessoal do Facilitador.
2. Consolida com clareza os pontos de concordância e os pontos de desacordo irredutíveis.
3. Mapeia a tabela comparativa de trade-offs de ambas as abordagens.

### Gate 5: Saída de `DECISION` $\rightarrow$ `REFLECTION`
1. O `DecisionRecord` responde integralmente às 13 Perguntas de Rastreabilidade.
2. Define gatilhos objetivos e mensuráveis para revisão futura (*Review Triggers*).
3. Caso não seja possível recomendar uma alternativa com segurança, o status obrigatório é `INSUFFICIENT_EVIDENCE`.

### Gate 6: Saída de `REFLECTION` $\rightarrow$ `COMPLETED`
1. O `LearningReport` identifica os conceitos de computação/engenharia subjacentes ao problema.
2. Fornece conexões pedagógicas entre a teoria e a decisão tomada.
3. Fornece recomendações qualificadas de estudo e perguntas para reflexão do usuário.

---

## 4. Protocolo de Rollback de Fases

Quando uma inconsistência basilar ou premissa falsa for identificada em fases posteriores, o sistema executa um **Rollback Controlado**:

1. **Gatilho de Rollback**:
   - Durante a Fase 2 (`CONFRONTATION`), o Auditor constata que uma premissa fundamental aceita na Fase 0 é categoricamente falsa ou impossível, invalidando ambas as propostas.
2. **Execução do Rollback**:
   - A máquina de estados dispara o evento `PHASE_ROLLBACK`.
   - O estado atual transiciona para `ROLLED_BACK`, gravando uma entrada imutável no log de auditoria explicando o motivo técnico do retrocesso.
   - O estado subsequente é automaticamente definido como `INVESTIGATION` (ou `WAITING_FOR_USER` se for necessário consultar o usuário diretamente).
3. **Preservação de Histórico**:
   - Os artefatos gerados nas fases abortadas (`Proposal v1`, `AuditReport v1`) **não são apagados**. Eles são marcados com a tag `SUPERSEDED_BY_ROLLBACK` para garantir a rastreabilidade completa do erro de projeto diagnosticado.

---

## 5. Pontos de Intervenção Humana (*Human-in-the-Loop*)

O usuário humano possui autoridade para intervir nos seguintes pontos:
* **Interação Ordinária**: Responder às dúvidas na Fase 0 (`WAITING_FOR_USER`).
* **Contestação de Premissas**: O usuário pode rejeitar uma premissa formulada pelo Facilitador antes da Fase 1 ser iniciada.
* **Solicitação de Rodada Suplementar**: Após a Fase 5, o usuário pode rejeitar a recomendação do Decisor e solicitar uma nova rodada de divergência com restrições adicionais.
* **Encerramento Compulsório**: O usuário pode acionar `USER_CANCELLED` em qualquer momento, congelando a sessão com status `CANCELLED`.
