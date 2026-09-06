# Casos de Teste Conceituais do Protocolo — AI Committee

Este documento formaliza cenários de validação rigorosos para testar a máquina de estados, o modelo de visibilidade e o protocolo de mensagens do **AI Committee**. Cada cenário atesta a conformidade das regras antes de qualquer implementação de código.

---

## Cenário 1: Contexto Completo (*Happy Path*)

### 1.1 Descrição do Problema
O usuário deseja definir a estratégia de cache para um portal de notícias de alto tráfego. Todas as restrições (orçamento de \$300/mês, infraestrutura AWS já existente com ECS Fargate, 5.000 req/s em pico, p95 < 50ms) e fatos estão completamente descritos na mensagem inicial.

### 1.2 Rastreio de Estados e Eventos
```
[DRAFT] 
  │  (Evento: SESSION_CREATED)
  ▼
[INVESTIGATION] 
  │  (Facilitador extrai Fatos, Restrições e Premissas sem perguntas pendentes)
  │  (Evento: CONTEXT_VALIDATED ──► Gera ProblemContext v1)
  ▼
[DIVERGENCE] 
  │  (Arquiteto produz PROP-ARCH-001:v1: Redis Cluster multi-AZ com invalidação por eventos)
  │  (Pragmático produz PROP-PRAG-001:v1: ElastiCache Redis Standalone com TTL agressivo)
  │  (Evento: PROPOSALS_CREATED)
  ▼
[CONFRONTATION] 
  │  (Auditor gera AUDIT-001:v1: Aponta risco de cold cache e SPOF no standalone do Pragmático)
  │  (Evento: AUDIT_COMPLETED)
  ▼
[DEFENSE] 
  │  (Arquiteto refina custos; Pragmático adiciona réplica de leitura para mitigar SPOF)
  │  (Evento: DEFENSES_SUBMITTED ──► Gera Defenses v1 e Propostas v2)
  ▼
[CONVERGENCE] 
  │  (Facilitador sintetiza matriz de trade-offs sem emitir juízo)
  │  (Evento: SYNTHESIS_CREATED ──► Gera DeliberationSynthesis v1)
  ▼
[DECISION] 
  │  (Decisor escolhe a Proposta do Pragmático refinada com réplica, fundamentando custo-benefício)
  │  (Evento: DECISION_RECORDED ──► Gera DecisionRecord [Status: RECOMMENDED])
  ▼
[REFLECTION] 
  │  (Mentor elabora guia sobre Cache Invalidation, Thundering Herd Problem e TTL)
  │  (Evento: LEARNING_REPORT_CREATED ──► Gera LearningReport v1)
  ▼
[COMPLETED]
```

### 1.3 Pontos de Verificação (*Assertions*)
- `ProblemContext.open_questions` estava vazio ao sair de `INVESTIGATION`.
- Arquiteto e Pragmático não tiveram acesso à proposta um do outro durante `DIVERGENCE`.
- As propostas `v1` permaneceram preservadas e imutáveis após os refinamentos de `DEFENSE`.
- O `DecisionRecord` respondeu a todas as 13 perguntas de rastreabilidade.

---

## Cenário 2: Contexto Insuficiente (Interação Humana na Fase 0)

### 2.1 Descrição do Problema
O usuário solicita recomendação de banco de dados: *"Preciso escolher um banco de dados para meu novo app de delivery"*. Faltam volume estimado de transações, modelo de consistência exigido, prazo e limitações financeiras.

### 2.2 Rastreio de Estados e Eventos
```
[DRAFT]
  │  (Evento: SESSION_CREATED)
  ▼
[INVESTIGATION]
  │  (Facilitador detecta ausência de requisitos essenciais)
  │  (Facilitador formula 3 perguntas críticas: volume esperado, orçamento, necessidade ACID)
  │  (Evento: QUESTION_RAISED)
  ▼
[WAITING_FOR_USER] ◄── [Execução Pausada]
  │  (Usuário responde: 100 transações/minuto, orçamento até $100/mês, consistência financeira estrita)
  │  (Evento: USER_RESPONDED)
  ▼
[INVESTIGATION]
  │  (Facilitador incorpora respostas aos Fatos e Restrições; valida completude)
  │  (Evento: CONTEXT_VALIDATED ──► Gera ProblemContext v1)
  ▼
[DIVERGENCE] ──► ... [Segue fluxo normal até COMPLETED]
```

### 2.3 Pontos de Verificação (*Assertions*)
- O sistema bloqueou a transição para `DIVERGENCE` enquanto as perguntas críticas não foram sanadas.
- O Facilitador não inventou nem alucinou métricas arbitrárias de escala.
- As respostas do usuário foram incorporadas como `Facts` e `Constraints`, e não como meras suposições.

---

## Cenário 3: Descoberta de Risco Bloqueante na Auditoria (*Rollback*)

### 3.1 Descrição do Problema
Discussão sobre arquitetura de telemetria em tempo real para dispositivos de IoT industrial. Na Fase 0, foi assumida a premissa de que os dispositivos teriam conexão de fibra ótica contínua. Na Fase 2, o Auditor identifica que o parque fabril opera em mineração subterrânea com quedas de conectividade de até 72 horas.

### 3.2 Rastreio de Estados e Eventos
```
[DIVERGENCE] ──► Gera Propostas baseadas em streaming contínuo WebSocket/gRPC
  │  (Evento: PROPOSALS_CREATED)
  ▼
[CONFRONTATION]
  │  (Auditor identifica que a premissa de conectividade contínua é fatal e impraticável no ambiente real)
  │  (Auditor atesta que ambas as propostas falham totalmente por falta de persistência local / store-and-forward)
  │  (Evento: PHASE_ROLLBACK ──► Registra justificativa técnica do rollback)
  ▼
[ROLLED_BACK]
  │  (Sistema invalida o avanço para a Fase 3; marca propostas v1 como SUPERSEDED_BY_ROLLBACK)
  ▼
[INVESTIGATION] (ou WAITING_FOR_USER)
  │  (Facilitador adiciona restrição dura de operação offline-first e solicita validação do usuário)
  │  (Evento: CONTEXT_VALIDATED ──► Gera ProblemContext v2)
  ▼
[DIVERGENCE] ──► Reinício da Fase 1 com novas propostas orientadas a Store-and-Forward
```

### 3.3 Pontos de Verificação (*Assertions*)
- O Auditor não tentou "consertar" o problema sozinho; acionou formalmente o portão de rollback.
- As propostas v1 da rodada abortada continuam no log histórico com hash e motivo do descarte.
- O `ProblemContext` foi atualizado para v2 e o novo ciclo de divergência respeitou a nova restrição.

---

## Cenário 4: Propostas Praticamente Equivalentes (Sem Falso Conflito)

### 4.1 Descrição do Problema
Escolha de ferramenta de CI/CD para uma equipe de 3 pessoas em um repositório GitHub. O Arquiteto propõe GitHub Actions com pipelines modulares e reusáveis; o Pragmático propõe GitHub Actions com workflow único simplificado.

### 4.2 Rastreio de Estados e Eventos
```
[DIVERGENCE]
  │  (Ambos convergem de forma independente para a mesma tecnologia base: GitHub Actions)
  │  (Evento: PROPOSALS_CREATED)
  ▼
[CONFRONTATION]
  │  (Auditor constata que não há divergência de stack; a diferença reside apenas no nível de modularização)
  │  (Evento: AUDIT_COMPLETED)
  ▼
[DEFENSE] ──► [Refinamentos menores]
  ▼
[CONVERGENCE]
  │  (Facilitador constata e explicita o consenso basilar: GitHub Actions é a escolha unânime)
  │  (Facilitador mapeia a divergência residual exclusivamente como trade-off de esforço de manutenção inicial vs futuro)
  │  (Evento: SYNTHESIS_CREATED)
  ▼
[DECISION]
  │  (Decisor adota a abordagem progressiva: workflow simples hoje [Pragmático] com gatilho para modularização [Arquiteto])
  │  (Evento: DECISION_RECORDED)
  ▼
[REFLECTION] ──► ... ──► [COMPLETED]
```

### 4.3 Pontos de Verificação (*Assertions*)
- Os agentes não fabricaram atrito artificial ou divergência fictícia onde havia consenso natural.
- O Facilitador não tentou esconder que ambas as propostas convergiam para a mesma ferramenta.
- O Decisor usou a tensão entre os papéis para formular uma estratégia evolutiva com gatilho claro de reavaliação.

---

## Cenário 5: Ausência de Evidências Suficientes (`INSUFFICIENT_EVIDENCE`)

### 5.1 Descrição do Problema
Migração de um core bancário legado com 30 anos de regras em Cobol não documentadas. O usuário deseja saber se deve refazer o sistema do zero em Go ou usar ferramentas de transpilação automatizada para Java. Não há cobertura de testes, métricas de transações nem inventário completo das rotinas legadas.

### 5.2 Rastreio de Estados e Eventos
```
[DIVERGENCE] ──► Arquiteto propõe reescrita orientada a microsserviços; Pragmático propõe transpilação
  ▼
[CONFRONTATION] ──► Auditor expõe que ambas as opções possuem risco de falha catastrófica incalculável
  ▼
[DEFENSE] ──► Proponentes não conseguem apresentar garantias de integridade de dados sem inventário
  ▼
[CONVERGENCE] ──► Facilitador atesta que as incógnitas (*Unknowns*) superam os Fatos
  ▼
[DECISION]
  │  (Decisor avalia que escolher qualquer alternativa representaria uma aposta cega irresponsável)
  │  (Decisor RECUSA indicar uma alternativa vencedora)
  │  (Evento: DECISION_FAILED)
  ▼
[INSUFFICIENT_EVIDENCE]
  │  (Gera DecisionRecord formal com status: INSUFFICIENT_EVIDENCE)
  │  (Documenta as informações que precisariam ser levantadas para viabilizar uma deliberação segura)
  │  (Define recomendações de provas de conceito exploratórias)
```

### 5.3 Pontos de Verificação (*Assertions*)
- O Decisor não "chutou" uma solução nem utilizou um sistema arbitrário de pontos para fingir certeza.
- O status formal do registro foi gravado como `INSUFFICIENT_EVIDENCE`.
- O dossiê final detalhou com rigor exatamente o que precisa ser descoberto antes de reabrir o comitê.
