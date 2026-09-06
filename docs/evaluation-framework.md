# Framework de Avaliação de Qualidade Deliberativa — AI Committee

Este documento define a arquitetura, os princípios, os critérios objetivos e o funcionamento do framework interno de avaliação de qualidade de deliberações do **AI Committee**.

---

## 1. Visão Geral e Princípios Fundamentais

O propósito do AI Committee não é apenas gerar um fluxo sintaticamente válido de mensagens entre LLMs, mas produzir uma **deliberação técnica genuína**, caracterizada por atrito dialético, transparência sobre trade-offs, auditoria impiedosa de riscos e soberania do tomador de decisão humano.

### 1.1. Validação Estrutural vs. Qualidade Deliberativa

O sistema opera em duas camadas de controle complementares:

```text
┌─────────────────────────────────────────────────────────────┐
│ 1. Validação Estrutural (Runtime)                           │
│    - Pydantic Models (tipos, campos obrigatórios, enums)     │
│    - State Machine & Transitions (fluxo de fases)           │
│    - Quality Gates (portais determinísticos de entrada/saída)│
│    - Event Store (integridade append-only e idempotência)   │
└──────────────────────────────┬──────────────────────────────┘
                               │ Garante integridade do processo
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Avaliação Deliberativa (Framework de Avaliação)          │
│    - Detecção de Falsos Conflitos (superficialidade)         │
│    - Verificação de Atrito Adversarial Real                 │
│    - Neutralidade Estrita do Facilitador                    │
│    - Rastreabilidade Genealógica da Decisão                 │
│    - Mensurabilidade Objetiva dos Gatilhos de Revisão        │
│    - Ancoragem Contextual do Roteiro Pedagógico             │
└─────────────────────────────────────────────────────────────┘
```

Um conjunto de artefatos pode ser 100% válido sob os schemas Pydantic e ainda assim constituir um **teatro de debate** (ex.: duas propostas idênticas usando palavras diferentes, um auditor que elogia em vez de criticar, ou um facilitador que direciona a decisão). O framework de avaliação foi construído para expor e penalizar essas falhas qualitativas.

---

## 2. Escala de Avaliação e Estrutura de Evidências

Todas as avaliações no framework seguem uma escala contínua normalizada de 0.0 a 5.0:

| Pontuação | Nível | Significado | Status de Aprovação |
| :---: | :---: | :--- | :---: |
| **0.0 - 0.9** | **Ausente** | Elemento não existe, violação crítica de protocolo ou falsificação. | **Reprovado** |
| **1.0 - 1.9** | **Fraco** | Tratamento puramente superficial, genérico ou simbólico. | **Reprovado** |
| **2.0 - 2.9** | **Parcial** | Atende a requisitos mínimos, mas carece de substância ou completude. | **Reprovado** |
| **3.0 - 3.9** | **Adequado** | Deliberação sólida, atende aos critérios fundamentais com evidências claras. | **Aprovado** (Threshold mínimo: 3.0) |
| **4.0 - 4.9** | **Forte** | Análise profunda, atrito dialético bem sustentado e trade-offs nítidos. | **Aprovado** |
| **5.0** | **Excelente** | Rigor técnico exemplar, completude formal e cobertura exaustiva de riscos. | **Aprovado** |

### 2.1. Princípio da Evidência Compulsória
Nenhum critério pode receber pontuação sem que uma lista de evidências observáveis (`evidence: list[str]`) seja extraída diretamente do histórico da sessão (`SessionView` / Event Store). Opiniões sem âncora textual são proibidas.

---

## 3. Os 12 Critérios de Avaliação

O framework avalia a deliberação segundo 12 dimensões canônicas, implementadas em `src/committee/evaluation/criteria.py`:

### 3.1. `PROPOSAL_DIVERGENCE` (Divergência entre Propostas)
* **Objetivo**: Garantir que a Fase 1 produza alternativas genuinamente concorrentes, e não variações cosméticas da mesma ideia.
* **Métrica Determinística**:
  * Divergência de complexidade arquitetural (`O(1)` vs `O(N)`), esforço estimado e reversibilidade.
  * Similaridade lexical (Jaccard) entre os textos de justificativa e abordagem técnica.
  * **Regra de Falso Conflito (`F-DIV-FALSE-CONFLICT`)**: Se a similaridade for muito alta e as métricas de esforço/complexidade forem idênticas, a pontuação é rebaixada para o nível Fraco (`1.0`), gerando finding de severidade `HIGH`.

### 3.2. `ASSUMPTION_COVERAGE` (Explicitação de Premissas)
* **Objetivo**: Verificar se as propostas identificam claramente premissas técnicas/operacionais e suas respectivas condições de invalidação.
* **Métrica Determinística**: Presença de premissas declaradas (`assumptions`) e condições sob as quais deixam de ser válidas (`invalidation_conditions`). Propostas sem condições de invalidação recebem penalidade.

### 3.3. `RISK_COVERAGE` (Cobertura de Riscos)
* **Objetivo**: Avaliar a profundidade do mapeamento de falhas operacionais e estruturais.
* **Métrica Determinística**: Presença de pontos únicos de falha declarados (`SPOFs`), análise de custos ocultos e identificação explícita de riscos de *overengineering* ou *underengineering*.

### 3.4. `ADVERSARIAL_QUALITY` (Qualidade Adversarial da Crítica)
* **Objetivo**: Verificar se o Auditor/SRE atuou com rigor técnico impiedoso em vez de emitir elogios condescendentes.
* **Métrica Determinística**: Contagem e severidade dos achados de auditoria (`HIGH`, `CRITICAL`). Penalização severa se o relatório contiver menos de 2 achados fundamentados ou ausência de modos de falha plausíveis.

### 3.5. `DEFENSE_RESPONSIVENESS` (Responsividade das Defesas)
* **Objetivo**: Assegurar que os proponentes (Arquiteto e Pragmático) responderam substantivamente a cada crítica do Auditor, e não apenas ignoraram os apontamentos.
* **Métrica Determinística**: Proporção de achados do auditor referenciados por ID nas defesas (`finding_responses`) e existência de refinamentos de versão v2 (`concessions_or_refinements`).

### 3.6. `SYNTHESIS_NEUTRALITY` (Neutralidade da Síntese)
* **Objetivo**: Garantir que o Facilitador permaneceu estritamente neutro na Fase 3, sem direcionar ou antecipar o veredito.
* **Regra de Falha Crítica (`F-SYN-BIASED-FACILITATOR`)**:
  * Busca determinística por expressões opinativas direcionadas na síntese (ex.: "recomendo a proposta", "a melhor opção é", "devemos adotar", "concluo que a proposta").
  * **Se violada**: Score imediato **0.0**, severidade `CRITICAL`. O facilitador violou seu mandato fundamental.

### 3.7. `TRADE_OFF_EXPLICITNESS` (Explicitação de Trade-offs)
* **Objetivo**: Evitar soluções milagrosas. Toda escolha de engenharia exige sacrifícios deliberados.
* **Métrica Determinística**: Presença de cláusulas estruturadas de ganhos (`gains`) versus sacrifícios (`sacrifices`). Penalização caso a decisão omita o que foi deliberadamente renunciado.

### 3.8. `DECISION_TRACEABILITY` (Rastreabilidade da Decisão)
* **Objetivo**: Garantir que a recomendação final decorre do debate contraditório e das propostas que passaram pelo crivo da auditoria.
* **Regra de Alternativa Fantasma (`F-TRC-UNTRACEABLE-ALTERNATIVE`)**:
  * A alternativa recomendada deve coincidir com uma das propostas submetidas na Fase 1/3 (`PROPOSAL_ARCHITECT` ou `PROPOSAL_PRAGMATIC`) ou ser justificada formalmente como síntese derivada.
  * Se a decisão escolher uma terceira via nunca debatida, é gerado finding de severidade `CRITICAL` e penalização para nível Fraco (`1.0`).

### 3.9. `DEBT_EXPLICITNESS` (Explicitação de Dívidas)
* **Objetivo**: Documentar conscientemente as dívidas técnicas e operacionais assumidas pela organização ao implementar a decisão.
* **Métrica Determinística**: Contagem de dívidas técnicas e operacionais documentadas com impacto e plano de mitigação/pagamento.

### 3.10. `REVIEWABILITY` (Reavaliabilidade e Gatilhos Objetivos)
* **Objetivo**: Proteger a organização contra decisões eternizadas fora de seu contexto de validade.
* **Métrica Determinística**: Os gatilhos de revisão (`review_triggers`) devem conter condições mensuráveis, métricas explícitas e limites numéricos (`thresholds`), em vez de descrições vagas como "quando crescer".

### 3.11. `LEARNING_VALUE` (Valor Pedagógico)
* **Objetivo**: Avaliar se o Mentor conectou o problema prático aos fundamentos teóricos da computação e diagnosticou lacunas reais do usuário.
* **Métrica Determinística**:
  * Mapeamento de lacunas cognitivas com evidências do diálogo (`context_evidence`).
  * Conexões explícitas teoria-prática e referências bibliográficas qualificadas.
  * Penalização para respostas que apenas repetem chavões genéricos.

### 3.12. `HUMAN_SOVEREIGNTY` (Soberania do Usuário Humano)
* **Objetivo**: Preservar a natureza estritamente consultiva do sistema, garantindo que o usuário mantenha o controle e a responsabilidade.
* **Métrica Determinística**: Verificação do status consultivo da decisão (`consultative`), presença de ressalvas de soberania humana e respeito aos pontos de intervenção do usuário.

---

## 4. Benchmark Scenarios e ScenarioRegistry

O framework disponibiliza uma suíte de 8 cenários canônicos de teste (`ScenarioRegistry`), permitindo aferir a sensibilidade do avaliador perante deliberações de diferentes qualidades:

| ID do Cenário | Nome | Comportamento Simulado | Resultado Esperado |
| :--- | :--- | :--- | :---: |
| `scenario-01-different-solutions` | Soluções Diferentes | Arquiteto (Microserviços) vs Pragmático (Monólito modular). Auditoria profunda, defesas ativas, síntese neutra e decisão rastreável. | **Aprovado** (Score ~4.8) |
| `scenario-02-false-conflict` | Falso Conflito | Propostas idênticas com redações levemente alteradas (duas propostas monólitas com mesmo esforço e reversibilidade). | **Reprovado** em Divergência (`F-DIV-FALSE-CONFLICT`) |
| `scenario-03-superficial-auditor` | Auditor Superficial | Auditoria complacente sem achados críticos ou SPOFs documentados. | **Reprovado** em Qualidade Adversarial (`F-ADV-NO-CRITICAL-FINDINGS`) |
| `scenario-04-strong-auditor` | Auditoria Rigorosa | Auditor identifica múltiplos SPOFs e riscos de saturação de conexão. | **Aprovado** em Qualidade Adversarial (Score 5.0) |
| `scenario-05-biased-facilitator` | Facilitador Parcial | Facilitador inclui recomendação explícita na síntese da Fase 3. | **Falha Crítica** (`F-SYN-BIASED-FACILITATOR`, Score 0.0) |
| `scenario-06-untraceable-decision` | Decisão Não Rastreável | Decisor recomenda uma alternativa que nunca foi debatida nem auditada. | **Falha Crítica** (`F-TRC-UNTRACEABLE-ALTERNATIVE`, Score 1.0) |
| `scenario-07-insufficient-evidence` | Evidência Insuficiente | O comitê reconhece falta de dados críticos e emite `INSUFFICIENT_EVIDENCE` com honestidade. | **Aprovado** (Honestidade Intelectual preservada) |
| `scenario-08-generic-mentor` | Mentor Genérico | Mentor responde com chavões técnicos genéricos sem citar evidências do histórico da sessão. | **Reprovado** em Valor Pedagógico (`F-LRN-GENERIC-MENTOR`) |

### 4.1. Como Executar os Cenários de Benchmark

```python
from committee.evaluation import DeterministicEvaluator, ScenarioRegistry

evaluator = DeterministicEvaluator()

# Avaliar um cenário específico
scenario = ScenarioRegistry.get("scenario-01-different-solutions")
session = scenario.setup()
result = evaluator.evaluate(session)

print(f"Status: {'Aprovado' if result.passed else 'Reprovado'}")
print(f"Score: {result.summary.overall_score:.2f}/5.0")
```

### 4.2. Como Registrar Novos Cenários

Para registrar novos cenários de teste na suíte de regressão:

```python
from committee.evaluation import BenchmarkScenario, ScenarioRegistry

def setup_custom_session():
    # Cria e popula a sessão usando a State Machine determinística
    ...
    return session

custom_scenario = BenchmarkScenario(
    id="scenario-09-custom-case",
    name="Nome Descritivo do Cenário",
    description="Explicação da dinâmica testada",
    expected_outcome=True,
    setup_fn=setup_custom_session,
    metadata={"categoria": "edge_cases"}
)

ScenarioRegistry.register(custom_scenario)
```

---

## 5. Estratégia de Evolução: Deterministic -> LLM Judge -> Hybrid

O framework foi projetado segundo uma hierarquia modular de avaliadores:

```text
               ┌────────────────────────┐
               │     BaseEvaluator      │ (Protocolo Abstrato)
               └───────────┬────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
┌──────────────────┐ ┌───────────┐ ┌───────────────────┐
│  Deterministic   │ │    LLM    │ │      Hybrid       │
│    Evaluator     │ │   Judge   │ │     Evaluator     │
│ (Implementado)   │ │  (Futuro) │ │     (Futuro)      │
└──────────────────┘ └───────────┘ └───────────────────┘
```

1. **`DeterministicEvaluator` (Camada Base Atual)**:
   - Execução em sub-segundo, sem custos de API e com 100% de repetibilidade.
   - Aplica regras estruturais, comparações léxicas, métricas heurísticas e barreiras invioláveis (ex.: viés do facilitador, rastreabilidade genealógica da alternativa).
2. **`LLMEvaluator` (Futura Extensão)**:
   - Utilizará um LLM com prompt de juiz para avaliar a sutileza conceitual, a plausibilidade técnica dos contra-argumentos e o grau de profundidade pedagógica.
3. **`HybridEvaluator` (Estratégia Final)**:
   - O `DeterministicEvaluator` opera como pré-filtro obrigatório. Se houver falha crítica (ex.: quebra de rastreabilidade ou viés), a sessão é imediatamente reprovada sem custo de tokens de julgamento.
   - O `LLMEvaluator` refina as notas dos cenários que passaram pelos gates determinísticos.

---

## 6. Prevenção de Regressões em CI/CD

O framework garante a reprodutibilidade e a integridade da governança dialética através de testes automatizados executados pelo `pytest`:

```bash
# Executar a suíte completa de avaliação
PYTHONPATH=. pytest -v tests/evaluation/

# Executar testes específicos dos 12 critérios
PYTHONPATH=. pytest -v tests/evaluation/test_criteria.py

# Validar os 8 cenários de benchmark
PYTHONPATH=. pytest -v tests/evaluation/test_scenarios.py
```

Quando novos prompts forem adicionados aos agentes (`agents/*.md`) ou quando novos modelos forem conectados, o `ScenarioRegistry` e os critérios determinísticos atuarão como guardiões da qualidade técnica, impedindo que degradações na capacidade de raciocínio ou no alinhamento dos agentes passem despercebidas.

---

## 7. Exemplo de Relatório de Avaliação

Abaixo está um exemplo de saída produzida pelo método `EvaluationResult.format_report()`:

```text
======================================================================
DELIBERATION EVALUATION REPORT
======================================================================
Scenario ID: scenario-01-different-solutions
Evaluated At: 2026-09-06T00:00:00+00:00
Overall Score: 4.83 / 5.00
Deliberation Status: APPROVED (Threshold: 3.00)
----------------------------------------------------------------------
CRITERIA BREAKDOWN:
  [PASS] proposal_divergence: 5.00/5.00
    - Evidência: Complexidade estrutural distinta: Architect=O(N) vs Pragmatic=O(1).
    - Evidência: Estimativas de esforço e reversibilidade divergentes.
  [PASS] assumption_coverage: 5.00/5.00
    - Evidência: Premissas identificadas com condições de invalidação claras.
  [PASS] risk_coverage: 5.00/5.00
    - Evidência: SPOFs e custos ocultos adequadamente mapeados.
  [PASS] adversarial_quality: 5.00/5.00
    - Evidência: 2 achados de severidade HIGH/CRITICAL identificados na auditoria.
  [PASS] defense_responsiveness: 4.50/5.00
    - Evidência: Proponentes responderam aos achados do auditor com refinamentos v2.
  [PASS] synthesis_neutrality: 5.00/5.00
    - Evidência: Facilitador manteve imparcialidade estrita; sem viés de recomendação.
  [PASS] trade_off_explicitness: 5.00/5.00
    - Evidência: Trade-offs explícitos com ganhos e sacrifícios declarados.
  [PASS] decision_traceability: 5.00/5.00
    - Evidência: Alternativa recomendada coincide com proposta auditada.
  [PASS] debt_explicitness: 4.50/5.00
    - Evidência: Dívidas técnicas e operacionais documentadas com impacto.
  [PASS] reviewability: 5.00/5.00
    - Evidência: Gatilhos de revisão mensuráveis com métricas e limites definidos.
  [PASS] learning_value: 4.50/5.00
    - Evidência: Lacunas cognitivas ancoradas em evidências do diálogo e teoria conectada.
  [PASS] human_sovereignty: 5.00/5.00
    - Evidência: Decisão consultiva com soberania humana preservada.
----------------------------------------------------------------------
STRENGTHS:
  + Divergência estrutural robusta entre as propostas iniciais.
  + Crítica adversarial rigorosa pelo Auditor/SRE.
  + Síntese perfeitamente neutra sem direcionamento de veredito.
  + Gatilhos de reavaliação objetivos com métricas quantitativas.
WEAKNESSES:
  (Nenhuma fraqueza crítica detectada)
CRITICAL FINDINGS:
  (Nenhum finding crítico)
======================================================================
