# Integração de Provedores de LLM — Google Gemini e OpenAI — AI Committee

Este documento descreve a arquitetura, o design de contratos, a taxonomia de erros, a segurança defensiva, a estratégia de structured output e a governança de execução da camada de provedores de LLM do **AI Committee**, abrangendo as implementações para **Google Gemini** e **OpenAI**.

---

## 1. Visão Geral e Princípios Arquiteturais

O AI Committee mantém desacoplamento rigoroso entre a inteligência deliberativa (agentes, máquinas de estados, event store) e os provedores concretos de modelos fundacionais.

O sistema **não** depende de plataformas específicas como o Google Antigravity ou frameworks pesados de terceiros (LangChain, CrewAI, AutoGen). Em vez disso, opera sob uma abstração orientada a protocolos puros e tipados:

```text
┌─────────────────────────────────────────────────────────────┐
│ Orchestrator / AgentRunner                                  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ LLMProvider (Protocol mínimo tipado)                        │
└──────────────┬──────────────────────────────┬───────────────┘
               │                              │
               ▼                              ▼
┌──────────────────────────────┐ ┌────────────────────────────┐
│ MockLLMProvider              │ │ Provedores Reais           │
│ (Testes determinísticos FSM) │ │ (Gemini & OpenAI)          │
└──────────────────────────────┘ └─────────────┬──────────────┘
                                               │
                       ┌───────────────────────┴───────────────────────┐
                       │                                               │
                       ▼                                               ▼
         ┌───────────────────────────┐                   ┌───────────────────────────┐
         │ GeminiLLMProvider         │                   │ OpenAILLMProvider         │
         │ (Google GenAI SDK Oficial)│                   │ (OpenAI SDK Oficial v3+)  │
         │ gemini-flash-latest       │                   │ gpt-4o / Responses API    │
         └───────────────────────────┘                   └───────────────────────────┘
```

A adição de novos provedores ou a substituição entre eles ocorre via fábrica `create_llm_provider()` ou injeção de dependência direta, sem alterar uma única linha de:
* Agentes especializados (`src/committee/agents/`);
* State Machine (`src/committee/state_machine.py`);
* Event Store append-only (`src/committee/event_store.py`);
* Quality Gates (`src/committee/gates.py`);
* Schemas canônicos (`schemas/`).

---

## 2. Configuração e Governança de Segredos

### 2.1. Variáveis de Ambiente Suportadas

A configuração é gerenciada de forma centralizada pela classe `LLMConfig` (`src/committee/llm/config.py`), que realiza leitura defensiva das variáveis de ambiente:

| Variável | Padrão | Descrição |
| :--- | :--- | :--- |
| `LLM_PROVIDER` | `gemini` | Identificador do provedor ativo (`openai`, `gemini` ou `mock`). |
| `LLM_MODEL` | *(None)* | Sobrescreve o modelo padrão do provedor ativo. |
| `OPENAI_API_KEY` | *(Obrigatória para OpenAI)* | Chave de API para autenticação na OpenAI (`sk-...`). |
| `OPENAI_MODEL` | `gpt-4o` | Modelo padrão utilizado no provedor OpenAI. |
| `OPENAI_TIMEOUT_SECONDS` | `60.0` | Timeout máximo em segundos para cada chamada à OpenAI. |
| `GEMINI_API_KEY` | *(Obrigatória para Gemini)* | Chave de API para autenticação no Google Gemini (`AIza...`). |
| `GOOGLE_API_KEY` | *(Fallback Gemini)* | Suporte à nomenclatura alternativa padrão do Google. |
| `GEMINI_MODEL` | `gemini-flash-latest` | Modelo padrão utilizado no provedor Gemini. |
| `GEMINI_TIMEOUT_SECONDS` | `60.0` | Timeout máximo em segundos para cada chamada ao Gemini. |
| `RUN_LIVE_LLM_TESTS` | `0` | Flag opt-in para habilitar testes de integração com APIs reais. |

### 2.2. Segurança e Mascaramento Compulsório
1. **API Keys Nunca são Commitadas**: Não existem chaves codificadas em arquivos do repositório.
2. **Defesa em `__repr__` e `__str__`**: As classes `LLMConfig`, `GeminiLLMProvider` e `OpenAILLMProvider` mascaram chaves (`sk-p...2345` / `AIza...3210`) ou as omitem completamente nas representações em string.
3. **Sanitização de Exceções**: A função `sanitize_secrets_from_text` intercepta mensagens de erro do SDK ou de rede (como headers de autorização `Bearer sk-...`, `x-goog-api-key`, parâmetros de URL `?key=...`) e redacta qualquer menção a chaves antes de propagar as exceções.
4. **Isolamento de Persistência**: Segredos jamais são gravados nos eventos do SQLite/WAL ou nos artefatos da sessão.

---

## 3. Structured Output e Desserialização Pydantic

O AI Committee rejeita terminantemente extração de informações via expressões regulares (*regex*) ou dependência de texto livre formatado em Markdown pelo LLM.

### 3.1. OpenAI: Responses API e Chat Completions com Structured Outputs
A OpenAI é integrada via SDK oficial `openai>=3.8.0`:
* **Caminho Primário — Responses API**: O método `client.responses.parse(text_format=output_schema, instructions=system_prompt, input=context_json)` retorna um `ParsedResponse` onde `output_parsed` já é uma instância validada do modelo Pydantic correspondente.
* **Caminho de Fallback — Chat Completions**: Se o endpoint de respostas retornar `NotFoundError` (ex.: modelos ou proxies que ainda não expõem `/responses`), o provedor executa fallback transparente para `client.chat.completions.parse(response_format=output_schema, ...)`.
* **Zero Alucinação de Estrutura**: Todos os 9 schemas canônicos utilizam `ConfigDict(extra="forbid")`, o que gera esquemas JSON estritos (`strict: True`, `additionalProperties: False`), garantindo conformidade matemática com os parsers da OpenAI.

### 3.2. Google Gemini: Adaptação com `clean_schema_for_gemini`
O SDK oficial `google-genai` recebe esquemas adaptados via `clean_schema_for_gemini()` para garantir compatibilidade com o OpenAPI 3.0 do endpoint do Gemini (ajustando `exclusiveMinimum` e desativando chamadas automáticas de função).

---

## 4. Taxonomia Unificada de Erros

Para manter a orquestração agnóstica a qualquer SDK concreto, todos os erros de provedores são mapeados para a taxonomia padrão (`src/committee/llm/exceptions.py`):

```text
                     ┌──────────────────────────────┐
                     │        ProviderError         │
                     └──────────────┬───────────────┘
       ┌──────────────┬─────────────┼──────────────┬──────────────┐
       ▼              ▼             ▼              ▼              ▼
┌──────────────┐┌──────────────┐┌────────────┐┌──────────────┐┌──────────────┐
│ProviderConfig││ProviderAuth  ││ProviderRate││ProviderTime  ││ProviderTemp  │
│urationError  ││entication    ││LimitError  ││outError      ││oraryError    │
│              ││Error         ││            ││              ││              │
└──────────────┘└──────────────┘└────────────┘└──────────────┘└──────────────┘
                                    │              │
                                    ▼              ▼
                             ┌──────────────┐┌──────────────┐
                             │ProviderResp  ││ProviderSchema│
                             │onseError     ││Error         │
                             └──────────────┘└──────────────┘
```

* **`ProviderConfigurationError`**: Chaves ausentes ou configuração inválida.
* **`ProviderAuthenticationError`**: Falha 401/403 de autenticação ou token revogado.
* **`ProviderRateLimitError`**: Limites de requisição atingidos (429).
* **`ProviderTimeoutError`**: Estouro de tempo limite de resposta.
* **`ProviderTemporaryError`**: Falhas de conexão, erros 5xx de servidor (transitórios).
* **`ProviderSchemaError`**: Falha na validação de schema ou recusa do modelo.
* **`ProviderResponseError`**: Resposta vazia ou ininteligível.

O `AgentRunner` utiliza essa taxonomia para gerenciar retries automáticos em falhas transitórias (`ProviderTemporaryError`, `ProviderRateLimitError`) sem depender de classes específicas de SDKs terceiros.

---

## 5. Telemetria de Uso e Custos

A cada invocação bem-sucedida, tanto o `OpenAILLMProvider` quanto o `GeminiLLMProvider` extraem métricas padronizadas em `last_metadata: LLMCallMetadata`:

* `model`: Nome exato do modelo executado (ex.: `gpt-4o`, `gemini-flash-latest`).
* `request_id`: Identificador único da requisição (quando fornecido pelo provedor).
* `latency_seconds`: Tempo total de round-trip em segundos (`time.perf_counter()`).
* `input_tokens`: Tokens de entrada consumidos.
* `output_tokens`: Tokens gerados no artefato.
* `total_tokens`: Soma total dos tokens da transação.

---

## 6. Fábrica Centralizada de Provedores

A instanciação de provedores é simplificada pela função `create_llm_provider`:

```python
from src.committee.llm.factory import create_llm_provider

# Provedor Mock para testes offline rápidos
mock_provider = create_llm_provider("mock")

# Provedor OpenAI real via variáveis de ambiente
openai_provider = create_llm_provider("openai")

# Provedor Gemini real via variáveis de ambiente
gemini_provider = create_llm_provider("gemini")
```

---

## 7. Como Executar os Testes e os Smoke Tests

### 7.1. Suíte Completa de Testes Determinísticos
```bash
PYTHONPATH=. .venv/bin/pytest -v
```

### 7.2. Testes Unitários dos Provedores (Sem Chamadas Externas)
```bash
# Testes do provedor OpenAI
PYTHONPATH=. .venv/bin/pytest -v tests/test_openai_provider.py

# Testes de substituição agnóstica de provedores
PYTHONPATH=. .venv/bin/pytest -v tests/test_provider_substitution.py

# Testes do provedor Gemini
PYTHONPATH=. .venv/bin/pytest -v tests/test_gemini_provider.py
```

### 7.3. Testes de Integração Reais (Opt-in)
```bash
# OpenAI Live
RUN_LIVE_LLM_TESTS=1 OPENAI_API_KEY="sua_chave_openai" PYTHONPATH=. .venv/bin/pytest -v tests/integration/test_openai_live.py

# Gemini Live
RUN_LIVE_LLM_TESTS=1 GEMINI_API_KEY="sua_chave_gemini" PYTHONPATH=. .venv/bin/pytest -v tests/integration/test_gemini_live.py
```

### 7.4. Smoke Tests Controlados
Scripts isolados que executam exclusivamente o `ArchitectAgent` sem persistir no Event Store:

```bash
# OpenAI Smoke Test
export OPENAI_API_KEY="sua_chave_openai"
PYTHONPATH=. .venv/bin/python scripts/smoke_test_openai.py

# Gemini Smoke Test
export GEMINI_API_KEY="sua_chave_gemini"
PYTHONPATH=. .venv/bin/python scripts/smoke_test_gemini.py
```
