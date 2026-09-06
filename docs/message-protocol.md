# Protocolo de Mensagens, Eventos e Artefatos — AI Committee

Este documento define a especificação técnica formal para envelopes de mensagens, catálogo de eventos, schemas estruturados de artefatos, regras de imutabilidade e mecanismos de intervenção humana no **AI Committee**.

---

## 1. Especificação do Envelope Canônico de Mensagem

Toda comunicação interna entre agentes, a engine e o usuário deve ser encapsulada em uma estrutura formal de envelope padronizada. Nenhuma mensagem transita como texto solto sem metadados.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "MessageEnvelope",
  "type": "object",
  "required": [
    "message_id",
    "session_id",
    "timestamp",
    "phase",
    "sender",
    "recipient",
    "event_type",
    "payload_schema",
    "payload",
    "artifact_version",
    "content_hash"
  ],
  "properties": {
    "message_id": { "type": "string", "format": "uuid" },
    "session_id": { "type": "string", "format": "uuid" },
    "correlation_id": { "type": ["string", "null"], "format": "uuid" },
    "timestamp": { "type": "string", "format": "date-time" },
    "phase": {
      "type": "string",
      "enum": [
        "PHASE_0_INVESTIGATION",
        "PHASE_1_DIVERGENCE",
        "PHASE_2_CONFRONTATION",
        "PHASE_3_DEFENSE",
        "PHASE_4_CONVERGENCE",
        "PHASE_5_DECISION",
        "PHASE_6_REFLECTION",
        "SYSTEM_INTERRUPTION"
      ]
    },
    "sender": {
      "type": "string",
      "enum": [
        "HUMAN_USER",
        "FACILITATOR",
        "ARCHITECT",
        "PRAGMATIST",
        "AUDITOR_SRE",
        "DECISOR",
        "MENTOR",
        "ORCHESTRATOR_ENGINE"
      ]
    },
    "recipient": {
      "type": "string",
      "enum": [
        "BROADCAST",
        "HUMAN_USER",
        "FACILITATOR",
        "ARCHITECT",
        "PRAGMATIST",
        "AUDITOR_SRE",
        "DECISOR",
        "MENTOR",
        "ORCHESTRATOR_ENGINE"
      ]
    },
    "event_type": { "type": "string" },
    "payload_schema": { "type": "string" },
    "payload": { "type": "object" },
    "artifact_version": { "type": "string", "pattern": "^v[0-9]+$" },
    "content_hash": { "type": "string", "pattern": "^sha256:[a-f0-9]{64}$" }
  }
}
```

---

## 2. Catálogo de Eventos do Sistema

| Evento | Emitido por | Fase | Significado / Propósito |
| :--- | :--- | :--- | :--- |
| `SESSION_CREATED` | `HUMAN_USER` / `ENGINE` | `PHASE_0_INVESTIGATION` | Inicialização da sessão com a entrada inicial do usuário. |
| `QUESTION_RAISED` | `FACILITATOR` | `PHASE_0_INVESTIGATION` | Solicitação de esclarecimento ou dado ausente dirigida ao usuário. |
| `USER_RESPONDED` | `HUMAN_USER` | `PHASE_0_INVESTIGATION` | Envio de respostas humanas às perguntas do Facilitador. |
| `CONTEXT_VALIDATED` | `FACILITATOR` | `PHASE_0_INVESTIGATION` | Congelamento do `ProblemContext` v1 e liberação da Fase 1. |
| `PROPOSAL_CREATED` | `ARCHITECT` / `PRAGMATIST` | `PHASE_1_DIVERGENCE` | Submissão de proposta técnica independente em regime cego. |
| `AUDIT_COMPLETED` | `AUDITOR_SRE` | `PHASE_2_CONFRONTATION` | Emissão do `AuditReport` com ataque às propostas e matriz de riscos. |
| `PHASE_ROLLBACK` | `AUDITOR_SRE` / `FACILITATOR` | `PHASE_2_CONFRONTATION` | Retrocesso para Fase 0 por detecção de falha basilar de premissa. |
| `DEFENSE_SUBMITTED` | `ARCHITECT` / `PRAGMATIST` | `PHASE_3_DEFENSE` | Submissão de resposta aos riscos da auditoria e refinamentos. |
| `SYNTHESIS_CREATED` | `FACILITATOR` | `PHASE_4_CONVERGENCE` | Mapeamento formal de consensos, dissensos e trade-offs. |
| `DECISION_RECORDED` | `DECISOR` | `PHASE_5_DECISION` | Registro da recomendação com trade-offs e gatilhos de revisão. |
| `DECISION_FAILED` | `DECISOR` | `PHASE_5_DECISION` | Atestado formal de insuficiência de evidência (`INSUFFICIENT_EVIDENCE`). |
| `LEARNING_REPORT_CREATED` | `MENTOR` | `PHASE_6_REFLECTION` | Registro do dossiê pedagógico e guia de estudo. |
| `USER_OVERRIDE` | `HUMAN_USER` | Qualquer Fase | Intervenção manual para ajustar restrição ou pedir nova rodada. |
| `SESSION_CANCELLED` | `HUMAN_USER` | Qualquer Fase | Cancelamento voluntário da sessão pelo usuário. |
| `CRITICAL_ERROR` | `ENGINE` | Qualquer Fase | Falha técnica operacional não recuperável. |

---

## 3. Especificação Estrutural dos Artefatos Canônicos

### 3.1 Artefato 1: `ProblemContext` (Fase 0)
```json
{
  "summary": "String descrevendo o problema em alto nível",
  "facts": [
    { "id": "F1", "description": "PostgreSQL 15 em instância única 16GB", "source": "Usuário" }
  ],
  "constraints": [
    { "id": "C1", "description": "Orçamento máximo de $200/mês", "type": "BUDGET", "negotiable": false },
    { "id": "C2", "description": "Prazo de entrega em 4 semanas", "type": "DEADLINE", "negotiable": false }
  ],
  "assumptions": [
    { "id": "A1", "description": "Volume de requisições permanecerá sob 200 req/s no primeiro trimestre", "risk_level": "MEDIUM" }
  ],
  "unknowns": [
    { "id": "U1", "description": "Latência média de serviço terceiro não informada", "impact_if_adverse": "HIGH" }
  ],
  "open_questions": [],
  "success_criteria": [
    "Latência p99 < 150ms",
    "Custo operacional previsível sob o orçamento delimitado"
  ]
}
```

---

### 3.2 Artefatos 2 e 3: `ArchitectProposal` e `PragmaticProposal` (Fase 1)
Ambas as propostas compartilham uma estrutura estritamente comparável:
```json
{
  "proposal_id": "PROP-ARCH-001",
  "proponent_role": "ARCHITECT",
  "title": "Arquitetura Modular Baseada em Eventos",
  "solution_overview": "Descrição abrangente da solução proposta",
  "technical_justification": "Por que esta solução é a mais adequada sob a ótica do papel",
  "benefits": ["Alta modularidade", "Escalabilidade independente de serviços"],
  "costs": {
    "implementation_effort": "HIGH",
    "infrastructure_cost_estimate": "$150-$180/mês"
  },
  "identified_risks": [
    "Complexidade de rastreabilidade distribuída",
    "Sobrecarga de governança de eventos"
  ],
  "operational_complexity": "MEDIUM_HIGH",
  "reversibility": {
    "score": "LOW",
    "rationale": "Migração de barramento de eventos exige refatoração profunda de contratos"
  },
  "future_consequences": "Facilita adição de novos consumidores sem alterar o produtor",
  "assumptions_used": ["A1"],
  "invalidation_conditions": [
    "Se o volume de eventos for inferior a 1 evento por minuto permanentemente"
  ]
}
```

---

### 3.3 Artefato 4: `AuditReport` (Fase 2)
```json
{
  "audit_id": "AUDIT-001",
  "critiques_proposal_a": [
    {
      "category": "OVERENGINEERING",
      "severity": "HIGH",
      "description": "Kafka/Event Bus introduz custo cognitivo desproporcional para o tráfego atual de 200 req/s."
    }
  ],
  "critiques_proposal_b": [
    {
      "category": "RESILIENCE",
      "severity": "MEDIUM",
      "description": "Acoplamento síncrono pode propagar cascata de falhas em caso de saturação do Postgres."
    }
  ],
  "single_points_of_failure": ["PostgreSQL sem réplica de leitura configurada"],
  "security_concerns": ["Falta de autenticação mTLS entre serviços internos"],
  "operational_concerns": ["Falta de observabilidade e tracing distribuído em A"],
  "hidden_costs": ["Custos de tráfego de rede inter-zonas não computados em A"],
  "fragile_assumptions": ["A premissa A1 de tráfego constante não possui margem para picos de campanhas de marketing"],
  "open_questions_for_proponents": [
    "Como a Proposta B lida com reinicializações do container durante picos?"
  ]
}
```

---

### 3.4 Artefatos 5 e 6: `ArchitectDefense` e `PragmaticDefense` (Fase 3)
```json
{
  "defense_id": "DEF-ARCH-001",
  "proponent_role": "ARCHITECT",
  "original_proposal_ref": "PROP-ARCH-001:v1",
  "critique_responses": [
    {
      "critique_ref": "OVERENGINEERING:Kafka",
      "stance": "CONCEDED_WITH_REFINEMENT",
      "rationale": "Reconhecemos o excesso do Kafka para a escala inicial. Substituímos por RabbitMQ leve ou Redis Streams.",
      "modifications": "Redução do footprint de infraestrutura de 3 brokers para 1 nó Redis com persistência AOF."
    },
    {
      "critique_ref": "HIDDEN_COSTS:Inter-zone",
      "stance": "CONTESTED",
      "rationale": "Todos os serviços estarão na mesma availability zone inicialmente, eliminando custo de tráfego inter-AZ."
    }
  ],
  "persistent_disagreements": [
    "Mantemos a rejeição a chamadas REST síncronas entre domínios críticos devido ao acoplamento temporal."
  ],
  "refined_proposal_version": "v2"
}
```

---

### 3.5 Artefato 7: `DeliberationSynthesis` (Fase 4)
```json
{
  "synthesis_id": "SYNTH-001",
  "consolidated_facts": ["PostgreSQL 15", "Budget $200", "Prazo 4 semanas"],
  "consolidated_constraints": ["Equipe de 2 engenheiros", "SLA p99 < 150ms"],
  "consolidated_assumptions": ["Tráfego inicial de 200 req/s com crescimento gradual"],
  "consolidated_unknowns": ["Latência da API terceira parceira sob pico"],
  "consensus_points": [
    "Ambos os proponentes concordam que persistência relacional básica atende o domínio de dados atual.",
    "Ambos concordam em descartar Kafka por custo desnecessário."
  ],
  "divergence_points": [
    "Comunicação síncrona simples (Pragmático) vs Mensageria assíncrona leve (Arquiteto refinado)."
  ],
  "strong_arguments_proposal_a": "Garante desacoplamento e facilidade para escalar novos consumidores sem refatorar o núcleo.",
  "strong_arguments_proposal_b": "Entrega em 2 semanas em vez de 4, com depuração trivial e sem necessidade de manter infraestrutura de filas.",
  "unresolved_risks": ["API terceira parceira pode se tornar gargalo compartilhado."],
  "trade_offs_matrix": [
    {
      "dimension": "Tempo de Entrega",
      "proposal_a": "3-4 semanas",
      "proposal_b": "1-2 semanas"
    },
    {
      "dimension": "Resiliência a Picos",
      "proposal_a": "Alta (Buffer em fila)",
      "proposal_b": "Média (Depende de rate limit e backpressure)"
    }
  ]
}
```

---

### 3.6 Artefato 8: `DecisionRecord` (Fase 5)
```json
{
  "decision_id": "DEC-001",
  "status": "RECOMMENDED",
  "winning_alternative": "Proposta Pragmática com Mitigações Críticas da Auditoria",
  "rejected_alternatives": [
    {
      "name": "Proposta do Arquiteto (Mensageria Assíncrona com Redis Streams)",
      "rejection_reason": "Prazo estrito de 4 semanas e equipe reduzida tornam a infraestrutura de mensageria um custo desnecessário no estágio atual de validação."
    }
  ],
  "technical_justification": "A solução síncrona atende com folga o critério de 200 req/s e cabe no orçamento com 50% de margem. As mitigações do Auditor (timeouts agressivos e circuit breaker) resolvem o risco de cascata.",
  "trade_offs_accepted": [
    { "gain": "Entrega em 10 dias úteis e custo infra de $40/mês", "sacrifice": "Acoplamento temporal temporário entre serviços" }
  ],
  "accepted_risks": [
    { "risk": "Falha na API terceira travará transações pontuais", "mitigation": "Circuit breaker com fallback gracioso" }
  ],
  "technical_debts": ["Necessidade futura de refatorar chamadas REST para mensageria quando o volume triplicar."],
  "operational_debts": ["Necessidade de monitoramento manual de latência de endpoints síncronos."],
  "critical_assumptions": ["Tráfego se mantém abaixo de 500 req/s."],
  "review_triggers": [
    "Tráfego médio ultrapassar 500 req/s por 3 dias consecutivos.",
    "A equipe de engenharia receber mais de 2 novos desenvolvedores.",
    "A API terceira apresentar latência p99 > 800ms com frequência."
  ],
  "confidence_level": "HIGH",
  "game_changing_missing_info": "Se a API terceira parceira não suportar idempotência, a decisão de circuit breaker precisará ser revista."
}
```

*Nota para Insuficiência de Evidências*: Caso `status` seja `INSUFFICIENT_EVIDENCE`, os campos `winning_alternative` e `technical_debts` tornam-se nulos, e o campo `game_changing_missing_info` passa a detalhar as lacunas intransponíveis que impediram a recomendação.

---

### 3.7 Artefato 9: `LearningReport` (Fase 6)
```json
{
  "report_id": "LRN-001",
  "technical_concepts": [
    "Circuit Breaker Pattern",
    "Acoplamento Temporal vs Espacial",
    "Backpressure e Degradação Graciosa",
    "Teorema CAP em Sistemas Monolíticos com I/O Externo"
  ],
  "concepts_required_to_understand": [
    "Diferença entre comunicação síncrona HTTP/gRPC e assíncrona orientada a eventos.",
    "Impacto de filas de conexões de banco de dados sob latência externa elevada."
  ],
  "identified_knowledge_gaps": [
    "O usuário demonstrou incerteza ao definir o comportamento do sistema quando um serviço externo está indisponível."
  ],
  "concepts_confused_during_debate": [
    "Confusão inicial entre alta disponibilidade (HA) e escalabilidade horizontal."
  ],
  "reflection_questions": [
    "Por que adicionar uma fila assíncrona não resolve magicamente um gargalo em um banco de dados relacional?",
    "Quais métricas de observabilidade mostram que um circuit breaker precisa ser disparado?"
  ],
  "recommended_learning_path": [
    { "topic": "Padrões de Resiliência", "reference": "Release It! (Michael Nygard), Cap. 4 e 5" },
    { "topic": "Fundamentos de Concorrência", "reference": "Designing Data-Intensive Applications (Martin Kleppmann), Cap. 11" }
  ],
  "theory_to_practice_connections": "A decisão tomada contratou acoplamento temporal deliberado (Pragmático) porque o custo de falha é menor que o custo de gerenciar transações distribuídas (Saga/Outbox) no momento."
}
```

---

## 4. Imutabilidade e Controle de Versão

1. **Append-Only Event Store**: Toda mudança é registrada por adição de novos eventos ao arquivo de log estruturado da sessão (`events.jsonl`). Eventos emitidos **nunca são atualizados nem removidos**.
2. **Versionamento Semântico de Artefatos**:
   - Propostas recebem versionamento progressivo (`v1`, `v2`).
   - Se uma proposta for refinada na Fase 3, a nova versão `v2` é gravada sem sobrescrever a `v1`.
   - O histórico de diffs entre `v1` e `v2` torna-se evidência rastreável da eficácia da auditoria.
3. **Hashes Criptográficos**: Cada envelope carrega `content_hash` gerado a partir do payload canônico serializado em JSON determinístico (chaves ordenadas), garantindo que os registros de deliberação sejam infalsificáveis.

---

## 5. Protocolo de Interação Humana

O usuário humano possui comandos reservados para intervir na máquina de deliberação:

* `USER_RESPOND`: Responde a perguntas formuladas pelo Facilitador em `WAITING_FOR_USER`.
* `USER_CONTEST_ASSUMPTION`: Permite ao usuário rejeitar ou alterar uma premissa mapeada antes que a deliberação avance para a Fase 1.
* `USER_REQUEST_REVISION`: Permite ao usuário, após visualizar o `DecisionRecord` da Fase 5, rejeitar a recomendação e solicitar uma nova rodada de divergência/defesa, injetando uma nova restrição mandatória.
* `USER_ABORT`: Encerra imediatamente a sessão, persistindo os artefatos gerados até aquele instante e definindo o estado da máquina como `CANCELLED`.
