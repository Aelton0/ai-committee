# Modelo Conceitual de Decisão — AI Committee

Este documento define a estrutura conceitual de dados, os requisitos de rastreabilidade e o formato canônico de registro de decisões geradas pelo **AI Committee**.

---

## 1. Requisitos de Rastreabilidade

Cada registro de decisão (*Decision Record*) produzido pelo comitê deve ser estritamente auditável e autossuficiente. O documento deve obrigatoriamente responder às **13 Perguntas Fundamentais de Rastreabilidade**:

1. **Qual era o problema?** (Contexto e impacto do desafio enfrentado).
2. **Quais eram as restrições?** (Limitações técnicas, orçamentárias, temporais ou regulatórias inegociáveis).
3. **Quais fatos estavam disponíveis?** (Dados verificados, métricas históricas e certezas objetivas).
4. **Quais eram as premissas adotadas?** (Suposições aceitas provisoriamente para viabilizar a análise).
5. **O que era desconhecido?** (Informações ausentes, incertezas identificadas e riscos do desconhecido).
6. **Quais soluções foram consideradas?** (Detalhamento das abordagens divergentes, no mínimo do Arquiteto e do Pragmático).
7. **Quais argumentos sustentaram cada solução?** (Racional técnico e benefícios projetados por cada proponente).
8. **Quais riscos foram identificados?** (Vulnerabilidades, SPOFs e falhas operacionais apontadas pelo Auditor/SRE).
9. **Quais trade-offs foram aceitos?** (O que foi ganho e o que foi deliberadamente sacrificado na escolha).
10. **Qual decisão foi tomada/recomendada?** (A recomendação formal sintetizada pelo Decisor e submetida ao usuário).
11. **Por que as alternativas foram rejeitadas?** (Justificativa técnica comparativa para o descarte de cada opção).
12. **Em quais condições a decisão deve ser reavaliada?** (Gatilhos objetivos e mensuráveis que invalidam o contexto atual).
13. **O que o usuário deveria aprender com essa decisão?** (Conceitos teóricos, padrões arquiteturais e plano de estudo extraídos pelo Mentor).

---

## 2. Taxonomia da Informação

Para garantir o princípio de não misturar certezas com suposições, o modelo conceitual classifica os dados em quatro categorias ontológicas:

```
                      ┌────────────────────────────────┐
                      │    Universo Informacional      │
                      └───────────────┬────────────────┘
                                      │
              ┌───────────────────────┴───────────────────────┐
              ▼                                               ▼
     [ Conhecimento Seguro ]                         [ Incerteza / Hipótese ]
              │                                               │
       ┌──────┴──────┐                                 ┌──────┴──────┐
       ▼             ▼                                 ▼             ▼
   [ FATOS ]   [ RESTRIÇÕES ]                    [ PREMISSAS ]  [ DESCONHECIDOS ]
  (Verificados (Limites fixos                     (Suposições    (Informações
   e objetivos) do contexto)                       adotadas)      ausentes)
```

* **Fato**: Informação objetiva, comprovada e observável no ambiente do usuário (ex.: "O banco atual é PostgreSQL 15 rodando em container único com 16GB de RAM").
* **Restrição**: Condição de contorno rígida imposta pela organização ou pelo negócio (ex.: "O orçamento mensal não pode ultrapassar \$200; o prazo de entrega é de 3 semanas").
* **Premissa**: Suposição razoável aceita como verdadeira para viabilizar a análise, mas sujeita a erro (ex.: "Assume-se que o tráfego não crescerá mais de 20% no próximo trimestre").
* **Desconhecido (*Unknown*)**: Informação necessária cuja resposta não está disponível no momento (ex.: "Desconhece-se a latência da API parceira sob pico de carga").

---

## 3. Estrutura do Registro de Decisão (*Decision Record Template*)

As decisões geradas na pasta `decisions/` obedecem à seguinte estrutura em Markdown (compatível com os futuros schemas Pydantic definidos em `schemas/`):

```markdown
# ADR-[ID]: [Título Conciso da Decisão]

* **Data da Deliberação**: YYYY-MM-DD
* **Status**: [Proposta | Recomendada | Aceita pelo Usuário | Rejeitada pelo Usuário | Obsoleta | INSUFFICIENT_EVIDENCE]
* **Sessão ID**: [Identificador único da sessão]
* **Facilitador**: Facilitador AI
* **Decisor**: Decisor AI

---

## 1. Contexto e Formulação do Problema
[Descrição clara do desafio, motivação e impacto no negócio/sistema.]

### 1.1 Fatos Verificados
* Fato 1: ...
* Fato 2: ...

### 1.2 Restrições Rígidas
* Restrição 1: ...
* Restrição 2: ...

### 1.3 Premissas e Hipóteses
* Premissa 1: ... (Justificativa para adoção)

### 1.4 Desconhecidos Identificados (Unknowns)
* Incógnita 1: ... (Impacto potencial caso se revele desfavorável)

---

## 2. Alternativas Analisadas

### Alternativa A: [Nome da Proposta do Arquiteto]
* **Proponente**: Arquiteto
* **Resumo da Abordagem**: ...
* **Argumentos de Sustentação**: ...
* **Críticas e Vulnerabilidades Apontadas pelo Auditor**: ...
* **Defesa e Refinamentos Aplicados**: ...

### Alternativa B: [Nome da Proposta do Pragmático]
* **Proponente**: Pragmático
* **Resumo da Abordagem**: ...
* **Argumentos de Sustentação**: ...
* **Críticas e Vulnerabilidades Apontadas pelo Auditor**: ...
* **Defesa e Refinamentos Aplicados**: ...

---

## 3. Decisão Recomendada

### 3.1 Proposta Escolhida
[Descrição detalhada da solução recomendada pelo comitê.]

### 3.2 Motivos da Escolha
[Fundamentação comparativa demonstrando por que esta opção melhor atende às restrições.]

### 3.3 Por que as Alternativas Foram Descartadas?
* **Alternativa A**: [Motivo do descarte parcial ou total]
* **Alternativa B**: [Motivo do descarte parcial ou total]

---

## 4. Trade-offs, Riscos e Dívidas

### 4.1 Trade-offs Aceitos
* **O que ganhamos**: ...
* **O que sacrificamos**: ...

### 4.2 Riscos Residuais e Mitigações
| Risco Identificado | Severidade | Estratégia de Mitigação |
| :--- | :--- | :--- |
| Exemplo: Saturação de conexões | Média | Adicionar pool de conexões (PgBouncer) |

### 4.3 Dívidas Técnicas e Operacionais Contratadas
* [Dívida 1]: Descrição do débito operacional ou técnico assumido e custo futuro de pagamento.

---

## 5. Gatilhos de Reavaliação (Review Triggers)

A decisão presente é válida exclusivamente sob o contexto atual e **deve ser obrigatoriamente reavaliada se**:
1. **Gatilho de Métrica**: Ex.: O volume de requisições ultrapassar 1.000 req/s por mais de 5 minutos contínuos.
2. **Gatilho de Infraestrutura**: Ex.: O custo de operação ultrapassar \$500/mês.
3. **Gatilho Temporal**: Ex.: Decorridos 6 meses do lançamento da versão inicial.
4. **Gatilho de Mudança de Restrição**: Ex.: A equipe de engenharia dobrar de tamanho ou surgir exigência de conformidade PCI-DSS.

---

## 6. Caderno de Aprendizado e Mentoria (Mentor)

### 6.1 Conceitos e Padrões Fundamentais
* **[Conceito 1]**: Explicação clara e desmistificada do padrão/conceito.
* **[Conceito 2]**: Conexão com os fundamentos de computação.

### 6.2 Diagnóstico de Lacunas do Usuário
* Observações construtivas sobre conceitos que o usuário demonstrou hesitação ou dúvida durante o debate.

### 6.3 Plano de Estudo e Referências
* [Leitura / Livro / Artigo Recomendado]: Por que ler e qual capítulo focar.
* [Exercício / Pergunta Reflexiva]: Desafio para o usuário fixar o modelo mental aprendido.
```

---

## 4. Preparação para Schemas de Dados

Na próxima etapa de implementação, este modelo será formalizado como schema computacional em `schemas/`:
* `DecisionRecord`: Schema unificado validando todos os campos obrigatórios.
* Tipagens de validação para `Fact`, `Constraint`, `Premise`, `Unknown`, `Alternative`, `Risk`, `TradeOff`, `ReviewTrigger` e `MentorshipDossier`.
