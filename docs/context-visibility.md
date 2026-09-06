# Modelo de Visibilidade de Contexto — AI Committee

Este documento define a especificação formal de isolamento de contexto, limites de informação e matriz de acesso aos artefatos durante todo o ciclo de deliberação do **AI Committee**.

---

## 1. Princípio de Isolamento e Não-Contaminação

O AI Committee opera sob o princípio de **necessidade estrita de conhecimento** (*Need-to-Know Principle*). Os agentes não compartilham uma janela de contexto global aberta. 

Cada agente, ao ser ativado em determinada fase, recebe uma projeção filtrada e higienizada do estado da deliberação. O vazamento de informações entre fases ou papéis é considerado uma falha crítica de integridade arquitetural, pois:
1. **Evita ancoragem cognitiva prematura**: Na divergência, proponentes não podem se influenciar mutuamente.
2. **Evita viés de confirmação e indulgência**: Na auditoria, o auditor não deve saber de defesas prévias ou tentativas de justificar falhas.
3. **Evita alucinação agregada**: Agentes não devem tentar resolver questões que competem a fases subsequentes.

---

## 2. Matriz Canônica de Visibilidade por Artefato

A tabela abaixo especifica o nível de acesso permitido para cada papel em relação aos artefatos canônicos do sistema:

| Artefato Canônico | Facilitador | Arquiteto | Pragmático | Auditor / SRE | Decisor | Mentor | Usuário Humano |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **ProblemContext** *(Fatos, Restrições, Premissas, Desconhecidos, Critérios)* | **Leitura/Escrita** | Leitura | Leitura | Leitura | Leitura | Leitura | **Leitura/Escrita** |
| **ArchitectProposal** *(Proposta Técnica A)* | Leitura | **Autor (Próprio)** | **PROIBIDO** | Leitura | Leitura | Leitura | Leitura |
| **PragmaticProposal** *(Proposta Técnica B)* | Leitura | **PROIBIDO** | **Autor (Próprio)** | Leitura | Leitura | Leitura | Leitura |
| **AuditReport** *(Relatório de Vulnerabilidades e Riscos)* | Leitura | Leitura *(apenas Fase 3+)* | Leitura *(apenas Fase 3+)* | **Autor (Próprio)** | Leitura | Leitura | Leitura |
| **ArchitectDefense** *(Defesa e Refinamentos A)* | Leitura | **Autor (Próprio)** | **PROIBIDO** | Leitura *(apenas Fase 4+)* | Leitura | Leitura | Leitura |
| **PragmaticDefense** *(Defesa e Refinamentos B)* | Leitura | **PROIBIDO** | **Autor (Próprio)** | Leitura *(apenas Fase 4+)* | Leitura | Leitura | Leitura |
| **DeliberationSynthesis** *(Síntese Estruturada do Debate)* | **Autor (Próprio)** | **PROIBIDO** | **PROIBIDO** | **PROIBIDO** | Leitura | Leitura | Leitura |
| **DecisionRecord** *(Recomendação ou Insufficient Evidence)* | Leitura | Leitura | Leitura | Leitura | **Autor (Próprio)** | Leitura | **Leitura/Aprovação** |
| **LearningReport** *(Dossiê Pedagógico e Roteiro de Estudo)* | Leitura | Leitura | Leitura | Leitura | Leitura | **Autor (Próprio)** | Leitura |

---

## 3. Especificação de Contexto e Proibições por Fase

### Fase 0 — Investigação
* **Papéis Ativos**: Facilitador e Usuário Humano.
* **Contexto Disponível**: Entrada bruta fornecida pelo usuário, perguntas de clarificação, respostas do usuário e histórico de sessões anteriores (se referenciado explicitamente).
* **Artefato Produzido**: `ProblemContext`.
* **Informações Proibidas**:
  - Sugestões de solução ou pré-julgamento de alternativas técnicas.
  - Alucinação de requisitos não validados pelo usuário.
  - Mistura de premissas não comprovadas como se fossem fatos verificados.

---

### Fase 1 — Divergência Cega (Blind Divergence)
* **Papéis Ativos**: Arquiteto e Pragmático (executados em isolamento mútuo estrito).
* **Contexto Disponível para Ambos**: Exclusivamente o `ProblemContext` validado na Fase 0 (contendo Fatos, Restrições, Premissas, Desconhecidos e Critérios de Sucesso).
* **Artefatos Produzidos**: `ArchitectProposal` e `PragmaticProposal`.
* **Informações Estritamente Proibidas**:
  - **Para o Arquiteto**: É proibido acessar o texto, ideias, rascunhos, custos ou estratégias da proposta do Pragmático.
  - **Para o Pragmático**: É proibido acessar o texto, ideias, rascunhos, diagramas ou estratégias da proposta do Arquiteto.
  - **Para Ambos**: É proibido consultar opiniões do Auditor ou tentar antecipar a recomendação do Decisor.

---

### Fase 2 — Confronto (Adversarial Critique & Risk Audit)
* **Papel Ativo**: Auditor / SRE.
* **Contexto Disponível**: `ProblemContext`, `ArchitectProposal` e `PragmaticProposal`.
* **Artefato Produzido**: `AuditReport`.
* **Informações Proibidas**:
  - Quaisquer respostas preliminares ou defesas orais dos proponentes.
  - Votos ou preferências de facilitação.
  - Modificação ou alteração dos textos das propostas originais submetidas.

---

### Fase 3 — Defesa e Refinamento
* **Papéis Ativos**: Arquiteto e Pragmático (agora expostos à auditoria, mantendo foco na sua linha).
* **Contexto Disponível para o Arquiteto**: `ProblemContext`, seu próprio `ArchitectProposal` e os trechos do `AuditReport` que dizem respeito à sua proposta (ou o relatório completo de auditoria para contexto comparativo de risco).
* **Contexto Disponível para o Pragmático**: `ProblemContext`, seu próprio `PragmaticProposal` e os trechos do `AuditReport` que dizem respeito à sua proposta (ou o relatório completo de auditoria).
* **Artefatos Produzidos**: `ArchitectDefense` e `PragmaticDefense`.
* **Regras de Imutabilidade**:
  - É **proibido reescrever retroativamente** a proposta da Fase 1 (`ArchitectProposal` v1 e `PragmaticProposal` v1 são imutáveis).
  - Mudanças devem ser declaradas formalmente como adendos ou versões refinadas (v2) referenciadas dentro da Defesa.
* **Informações Proibidas**:
  - Comunicação bilateral direta não mediada entre Arquiteto e Pragmático para combinar consensos ou ceder concessões informais.

---

### Fase 4 — Convergência
* **Papel Ativo**: Facilitador.
* **Contexto Disponível**: Conjunto completo de dados da deliberação até o momento: `ProblemContext`, `ArchitectProposal`, `PragmaticProposal`, `AuditReport`, `ArchitectDefense` e `PragmaticDefense`.
* **Artefato Produzido**: `DeliberationSynthesis`.
* **Informações Proibidas / Comportamento Vedado**:
  - É proibido ao Facilitador emitir uma decisão ou expressar preferência por uma alternativa.
  - É proibido ocultar discordâncias legítimas que persistiram após a Fase 3.
  - É proibido forçar um consenso artificial.

---

### Fase 5 — Decisão
* **Papel Ativo**: Decisor.
* **Contexto Disponível**: Todos os artefatos anteriores, com ênfase na `DeliberationSynthesis`, `AuditReport`, `ArchitectDefense` e `PragmaticDefense`.
* **Artefato Produzido**: `DecisionRecord`.
* **Regras de Avaliação**:
  - O Decisor não pode ignorar os riscos identificados pelo Auditor.
  - Se os dados disponíveis forem incoerentes ou insuficientes para garantir confiabilidade mínima, o Decisor é **terminantemente proibido** de inventar uma escolha; ele deve emitir o status `INSUFFICIENT_EVIDENCE`.

---

### Fase 6 — Reflexão Pedagógica
* **Papel Ativo**: Mentor.
* **Contexto Disponível**: Todos os artefatos gerados nas fases anteriores (0 a 5), incluindo o `DecisionRecord` e todo o histórico de perguntas/respostas com o usuário.
* **Artefato Produzido**: `LearningReport`.
* **Informações Proibidas / Diretrizes**:
  - É proibido fazer suposições depreciativas sobre a inteligência ou competência geral do usuário; o diagnóstico de lacunas deve se ater estritamente às dúvidas e evidências apresentadas na deliberação.
  - É proibido reabrir o debate técnico ou alterar a decisão tomada.

---

## 4. Mecanismos de Aplicação do Isolamento de Contexto

Para que a implementação futura da engine garanta determinismo e integridade, as seguintes regras técnicas devem ser seguidas:

1. **Injeção Atômica de Contexto**: A engine nunca deve passar referências a buffers compartilhados de mensagens completas. O prompt montado para a execução de cada agente deve conter apenas os artefatos explicitamente listados como permitidos nesta especificação.
2. **Higienização de Metadados**: Nomes de autores em mensagens internas durante fases cegas devem ser anonimizados se houver risco de contaminação cruzada.
3. **Auditoria de Vazamento**: Cada invocação de agente deve registrar um hash criptográfico das entradas injetadas, permitindo auditar a posteriori se houve violação de isolamento de contexto.
