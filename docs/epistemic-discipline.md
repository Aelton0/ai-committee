# Disciplina Epistêmica no AI Committee

Este documento formaliza os princípios, taxonomia, garantias arquiteturais, papéis dos agentes e critérios analíticos que compõem a camada de **Disciplina Epistêmica** do **AI Committee**.

---

## 1. O Problema: Indisciplina Epistêmica em LLMs

Modelos de linguagem possuem a tendência intrínseca de preencher lacunas de informação silenciosamente. Quando apresentados a um contexto com restrições mínimas, modelos com papéis de autoridade técnica (como arquitetos de software) tendem a:

1. **Inventar métricas quantitativas** (ex.: assumir que um sistema atende "50.000 req/s" ou "1 milhão de usuários" sem que isso tenha sido informado).
2. **Introduzir sofisticação desnecessária por padrão** (adotar Kafka, Kubernetes, service mesh ou sharding distribuído como reflexo pavloviano).
3. **Ocultar premissas e hipóteses** (tratar palpites sobre o futuro do produto como se fossem certezas operacionais).
4. **Ignorar incógnitas cruciais** (deixar de perguntar ou medir parâmetros vitais de saturação antes de emitir recomendações definitivas).

No AI Committee, essa falha não é tolerada nem tratada de forma cosmética. A Disciplina Epistêmica impõe que todo agente separe rigidamente o que é sabido, o que é suposto, o que é inferido e o que é desconhecido.

---

## 2. As 5 Categorias Epistêmicas Canônicas

Toda deliberação do comitê manipula entidades classificadas estritamente em uma das 5 categorias epistêmicas:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CATEGORIAS EPISTÊMICAS                             │
├─────────────────┬───────────────────────────────────────────────────────────┤
│ FACT            │ Fato verificado fornecido no ProblemContext ou medido     │
├─────────────────┼───────────────────────────────────────────────────────────┤
│ ASSUMPTION      │ Hipótese de trabalho declarada com condição de invalidação│
├─────────────────┼───────────────────────────────────────────────────────────┤
│ INFERENCE       │ Conclusão intermediária com rastreabilidade formal        │
├─────────────────┼───────────────────────────────────────────────────────────┤
│ UNKNOWN         │ Informação crítica ausente ou não mensurada               │
├─────────────────┼───────────────────────────────────────────────────────────┤
│ RECOMMENDATION  │ Ação técnica proposta (incondicional ou IF ... THEN ...)   │
└─────────────────┴───────────────────────────────────────────────────────────┘
```

### 2.1. Fato (`FACT`)
* **Definição**: Dado objetivo e comprovável presente no `ProblemContext` ou fornecido pelo usuário.
* **Exemplos**: "Banco PostgreSQL 15 rodando em db.m5.xlarge", "Orçamento de infraestrutura máximo de $400/mês", "Equipe de 3 engenheiros".
* **Regra**: Agentes jamais podem criar fatos novos. Qualquer alegação de métrica ausente no contexto é considerada uma violação crítica (`F-EPI-FACT-01`).

### 2.2. Premissa (`ASSUMPTION`)
* **Definição**: Hipótese de trabalho adotada provisoriamente para viabilizar o projeto diante de dados incompletos.
* **Exigência**: Toda premissa deve conter:
  1. `statement`: A hipótese clara.
  2. `reason`: Motivo técnico/operacional pelo qual a premissa é plausível.
  3. `confidence`: Nível de certeza (`LOW`, `MEDIUM`, `HIGH`).
  4. `invalidation_condition`: Condição mensurável que, se ocorrer, anula a premissa.
  5. `risk_level`: Impacto caso a premissa esteja incorreta.

### 2.3. Inferência (`INFERENCE`)
* **Definição**: Dedução lógica intermediária derivada exclusivamente de fatos ou premissas previamente declarados.
* **Exigência**: Deve conter o campo `depends_on`, referenciando expressamente os IDs dos fatos ou premissas suportantes (ex.: `["F1", "A1"]`).
* **Regra**: Inferências com dependências ausentes, quebradas ou não declaradas falham em `INFERENCE_TRACEABILITY` (`F-EPI-INF-01`).

### 2.4. Incógnita (`UNKNOWN`)
* **Definição**: Parâmetro essencial que é desconhecido, não medido ou temporariamente incognoscível.
* **Exemplos**: "Taxa de requisições de pico durante campanhas", "Tempo de resposta do gateway parceiro sob estresse".
* **Regra**: O agente deve reconhecer o `UNKNOWN`, avaliar o risco de sua incerteza e propor como medi-lo (`how_to_resolve`), sem tentar adivinhá-lo magicamente.

### 2.5. Recomendação Condicional (`RECOMMENDATION`)
* **Definição**: Proposta técnica de solução, que deve ser formulada sob guarda condicional caso a necessidade estrutural dependa de fatos ainda não provados.
* **Formato Canônico**:
  $$\text{IF } [\text{métrica / condição mensurável}] \text{ THEN } [\text{ação de alta complexidade}] \text{ ELSE } [\text{alternativa simples}]$$
* **Exemplo**:
  > "IF o throughput sustentado ultrapassar 2.000 req/s THEN particionar banco e adotar fila distribuída (Kafka) ELSE manter PostgreSQL com réplicas de leitura."

---

## 3. Mandato dos Agentes sob Disciplina Epistêmica

| Agente | Mandato Epistêmico Específico |
| :--- | :--- |
| **Arquiteto** | **Anti-sofisticação por padrão**: Projetar para o contexto real e comprovado. Se propor infraestrutura de alta complexidade (Kafka, K8s, sharding), deve obrigatória e formalmente justificar com FATOS do contexto ou guardar sob RECOMENDAÇÃO CONDICIONAL. Declarar formalmente `epistemic_section`. |
| **Pragmático** | **Anti-minimização ingênua de escala**: Não fingir que complexidade nunca existirá. Declarar premissas de volume e capacidade, explicitando os limites operacionais exatos em que a solução simples se esgota. |
| **Auditor / SRE** | **Auditoria de risco epistêmico (`EPISTEMIC_RISK`)**: Caçar premissas ocultas, verificar se o Arquiteto inventou números ou vazões, e auditar se os agentes respeitaram ou ignoraram os `UNKNOWN` cadastrados. |
| **Facilitator** | **Preservação de fronteiras epistêmicas na síntese**: Separar rigidamente fatos acordados de premissas divergentes e incógnitas remanescentes. Nunca sintetizar premissas como se fossem fatos. |
| **Decisor** | **Rastreabilidade e incerteza honesta**: Se dados essenciais estiverem ausentes e impedirem decisão confiável, emitir obrigatoriamente status `INSUFFICIENT_EVIDENCE`. Não forçar um vencedor artificial. Citar `supported_by` e formular planos condicionais. |
| **Mentor** | **Pedagogia epistêmica**: Ensinar o usuário a raciocinar sobre fatos versus suposições, apontando heurísticas para medir incógnitas e mitigar riscos de premissas frágeis. |

---

## 4. Os 6 Critérios Analíticos de Avaliação Epistêmica

O `DeterministicEvaluator` executa, além dos 12 critérios analíticos originais, 6 critérios determinísticos de Disciplina Epistêmica:

1. **`FACT_GROUNDING`**:
   - Analisa se todas as métricas quantitativas e afirmações factuais das propostas estão estritamente contidas no `ProblemContext`.
   - Penaliza claims arbitrários com nota 1.0/5.0 e finding crítico `F-EPI-FACT-01`.
2. **`ASSUMPTION_TRANSPARENCY`**:
   - Detecta no texto das propostas hipóteses operacionais não declaradas (como projeções de crescimento ou prazos de aprendizado).
   - Exige que toda hipótese seja registrada com condição de invalidação e razão técnica.
3. **`UNKNOWN_VISIBILITY`**:
   - Garante que as incógnitas declaradas no `ProblemContext` sejam visibilizadas, preservadas e discutidas nas propostas e decisões.
   - Penaliza severamente propostas que ignoram as incógnitas informadas pelo usuário.
4. **`INFERENCE_TRACEABILITY`**:
   - Valida a rastreabilidade estrutural: verifica se cada item de `inferences` aponta para IDs válidos e existentes em `facts` e `assumptions`.
5. **`RECOMMENDATION_GROUNDING`**:
   - Verifica se recomendações de infraestrutura pesada (Kafka, multi-região, sharding) são fundamentadas em fatos ou devidamente resguardadas por guardas condicionais (`IF ... THEN ...`).
6. **`EPISTEMIC_INTEGRITY`**:
   - Avaliação composta agregando as 5 dimensões. Caso ocorra uma violação grave (fato inventado, premissa oculta crítica), a nota geral de integridade é limitada a $\le 2.0/5.0$.

---

## 5. Cenários de Teste Canônicos (Benchmarks 09 a 14)

Os seguintes cenários em `src/committee/evaluation/scenarios.py` validam o rigor do motor:

* **`scenario-09-invented-fact`**: Proposta inventa claim de 50.000 req/s ausente no contexto $\rightarrow$ Falha em `FACT_GROUNDING` ($score \le 2.0$).
* **`scenario-10-hidden-assumption`**: Proposta utiliza premissa de 20% de crescimento e 2 semanas de curva de aprendizado sem declarar em `assumptions` $\rightarrow$ Falha em `ASSUMPTION_TRANSPARENCY` ($score \le 2.5$).
* **`scenario-11-explicit-assumption`**: Proposta declara explicitamente a premissa de 20% com condição de invalidação e impacto $\rightarrow$ Sucesso em `ASSUMPTION_TRANSPARENCY` ($score \ge 4.5$).
* **`scenario-12-unknown-ignored`**: Contexto possui incógnita de pico de campanha que é ignorada pelos agentes $\rightarrow$ Falha em `UNKNOWN_VISIBILITY` ($score \le 2.5$).
* **`scenario-13-conditional-recommendation`**: Proposta adota Kafka guardado por `IF throughput > 10.000 req/s THEN ... ELSE ...` $\rightarrow$ Sucesso em `RECOMMENDATION_GROUNDING` ($score \ge 4.5$).
* **`scenario-14-proper-uncertainty`**: Decisão com incógnitas não resolvidas emite honestamente `INSUFFICIENT_EVIDENCE` $\rightarrow$ Sucesso em `UNKNOWN_VISIBILITY` e `EPISTEMIC_INTEGRITY` ($score \ge 4.5$).

---

## 6. Como Executar os Smoke Tests

```bash
# Execução determinística simulada (sem chamadas a APIs externas)
PYTHONPATH=. .venv/bin/python scripts/smoke_test_epistemic.py --mock

# Execução real com modelo OpenAI (gpt-4o)
export OPENAI_API_KEY="sk-proj-sua-chave"
PYTHONPATH=. .venv/bin/python scripts/smoke_test_epistemic.py
```
