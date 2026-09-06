# Integração de Provedores de LLM — Google Gemini — AI Committee

Este documento descreve a arquitetura, o design de contratos, a segurança defensiva, a estratégia de structured output e a governança de execução da camada de provedores de LLM do **AI Committee**, com foco na implementação do **Google Gemini**.

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
│ MockLLMProvider              │ │ GeminiLLMProvider          │
│ (Testes determinísticos FSM) │ │ (Google GenAI SDK Oficial) │
└──────────────────────────────┘ └─────────────┬──────────────┘
                                               │
                                               ▼
                                 ┌────────────────────────────┐
                                 │ Google Gemini API          │
                                 │ (gemini-2.5-flash)         │
                                 └────────────────────────────┘
```

A adição de novos provedores (ex.: Anthropic, OpenAI, modelos locais via Ollama/vLLM) ocorrerá futuramente através de novas implementações de `LLMProvider`, sem alterar uma única linha de:
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
| `GEMINI_API_KEY` | *(Obrigatória em modo real)* | Chave de API para autenticação no Google Gemini. |
| `GOOGLE_API_KEY` | *(Fallback automático)* | Suporte à nomenclatura alternativa padrão do Google. |
| `LLM_PROVIDER` | `gemini` | Identificador do provedor ativo (`gemini` ou `mock`). |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Nome do modelo a ser utilizado nas deliberações. |
| `GEMINI_TIMEOUT_SECONDS` | `60.0` | Timeout máximo em segundos para cada chamada à API. |
| `RUN_LIVE_LLM_TESTS` | `0` | Flag opt-in para habilitar testes de integração com a API real. |

### 2.2. Segurança e Mascaramento Compulsório
1. **API Keys Nunca são Commitadas**: Não existem chaves codificadas em arquivos do repositório.
2. **Defesa em `__repr__` e `__str__`**: As classes `LLMConfig` e `GeminiLLMProvider` mascaram a chave (`AIza...3210`) ou a omitem completamente nas representações em string.
3. **Sanitização de Exceções**: A função `sanitize_secrets_from_text` intercepta mensagens de erro do SDK ou de rede (como URLs com `?key=...` ou headers `x-goog-api-key`) e redacta qualquer menção a chaves antes de propagar as exceções.
4. **Isolamento de Persistência**: Segredos jamais são gravados nos eventos do SQLite/WAL ou nos artefatos da sessão.

---

## 3. Structured Output e Desserialização Pydantic

O AI Committee rejeita terminantemente extração de informações via expressões regulares (*regex*) ou dependência de texto livre formatado em Markdown pelo LLM.

A extração de artefatos opera no seguinte pipeline determinístico:

```text
Contexto Sanitizado da Fase (JSON)
+
System Prompt Especializado do Agente
+
Schema Pydantic Alvo (Ex: ArchitectProposal)
               │
               ▼
   clean_schema_for_gemini()
               │
               ▼
   Google GenAI SDK (types.GenerateContentConfig)
     - response_mime_type: "application/json"
     - response_schema: OpenAPI/JSON Schema adaptado
               │
               ▼
   Google Gemini API (Inferência com Restrição Estrutural)
               │
               ▼
   Payload JSON Válido (sem Markdown ou alucinações de formato)
               │
               ▼
   Pydantic model_validate_json()
               │
               ▼
   Instância Tipada do Artefato Canônico
```

### 3.1. Adaptação de Schemas Pydantic v2 para Google GenAI
O Pydantic v2 gera especificações JSON Schema 2020-12 / OpenAPI 3.1 com o campo `exclusiveMinimum` para campos com validação estrita (ex.: `PositiveInt`, gerando `exclusiveMinimum: 0`). A biblioteca oficial `google-genai` valida o schema de saída contra `types.Schema` que rejeita campos extras com `extra_forbidden`.

Para sanar essa discrepância sem alterar os schemas fundamentais do domínio, a função utilitária `clean_schema_for_gemini()` realiza adaptações recursivas equivalentes:
* `exclusiveMinimum: N` (inteiro) $\rightarrow$ `minimum: N + 1` (ex.: `version > 0` torna-se `version >= 1`);
* `exclusiveMaximum: N` (inteiro) $\rightarrow$ `maximum: N - 1`;
* Remoção de metadados não reconhecidos pelo endpoint (ex.: `$schema`).

Todos os 9 schemas canônicos do AI Committee passam com 100% de conformidade sob o transformador da SDK oficial.

---

## 4. Timeout, Erros e Política de Retries

O provedor **não duplica a lógica de retries**. Ele reporta erros de forma transparente, permitindo que o `AgentRunner` mantenha autoridade total sobre o ciclo de tentativas:

```text
GeminiLLMProvider
       │
       ▼ (timeout ou falha de rede)
GeminiTimeoutError / GeminiAPIError (mensagem sanitizada)
       │
       ▼
AgentRunner
       │
       ▼
Retry Policy (tentativa 1 de 3 -> tentativa 2 de 3 -> sucesso)
```

* **`GeminiTimeoutError`**: Disparado quando a requisição excede `gemini_timeout_seconds`.
* **`GeminiAPIError`**: Disparado para falhas 4xx/5xx da API, bloqueios de segurança ou payload ininteligível.
* **`GeminiConfigurationError`**: Disparado imediatamente se nenhuma credencial válida for fornecida.

---

## 5. Telemetria de Uso e Custos

A cada invocação bem-sucedida, o `GeminiLLMProvider` extrai métricas de observabilidade de `response.usage_metadata` e armazena em `last_metadata: LLMCallMetadata`:

* `model`: Nome exato do modelo Gemini executado.
* `latency_seconds`: Tempo total de round-trip em segundos (medido via `time.perf_counter()`).
* `input_tokens`: Quantidade de tokens no prompt (`prompt_token_count`).
* `output_tokens`: Quantidade de tokens gerados no artefato (`candidates_token_count`).
* `total_tokens`: Soma total dos tokens consumidos.

Nenhum dado confidencial ou prompt de usuário é armazenado apenas para fins de telemetria.

---

## 6. Roteamento Futuro de Modelos

A arquitetura já suporta o mapeamento dinâmico de modelos por papel de agente via `LLMConfig.get_model_for_agent(role)`:

```python
config = LLMConfig(
    gemini_model="gemini-2.5-flash",
    agent_models={
        "ARCHITECT": "gemini-1.5-pro",
        "PRAGMATIST": "gemini-2.5-flash",
        "AUDITOR_SRE": "gemini-1.5-pro",
    }
)
```

Nesta fase inicial, todos os agentes utilizam o modelo padrão configurado (`gemini-2.5-flash`), preparando o sistema para roteamento diferenciado sem modificação nos agentes.

---

## 7. Como Executar os Testes e o Smoke Test

### 7.1. Testes Unitários Determinísticos (Sem Consumo de API)
Os testes unitários utilizam mocks do cliente da SDK e não realizam chamadas externas à internet:

```bash
PYTHONPATH=. .venv/bin/pytest -v tests/test_gemini_provider.py
```

### 7.2. Teste de Integração Real (Opt-in)
Executa uma chamada real ao Google Gemini gerando um `ArchitectProposal`:

```bash
export GEMINI_API_KEY="sua_chave_aqui"
export RUN_LIVE_LLM_TESTS=1
PYTHONPATH=. .venv/bin/pytest -v tests/integration/test_gemini_live.py
```

### 7.3. Smoke Test Controlado
Script isolado que executa exclusivamente o `ArchitectAgent`, sem persistir sessão no Event Store:

```bash
export GEMINI_API_KEY="sua_chave_aqui"
PYTHONPATH=. .venv/bin/python scripts/smoke_test_gemini.py
```

---

## 8. Limitações Atuais

1. **Sem Streaming**: A geração estruturada opera em modo bloco (*unary/non-streaming*), garantindo validação atômica do JSON pelo Pydantic antes de entregar o artefato ao runner.
2. **Telemetria Efêmera**: As métricas de token e latência residem em memória (`provider.last_metadata`) e ainda não são gravadas em banco de dados ou dashboard de observabilidade.
3. **Chave Única**: A configuração atual assume uma única chave de API para todos os membros do comitê.
