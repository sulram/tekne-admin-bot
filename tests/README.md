# Testes - Tekne Admin Bot

Estrutura organizada de testes para o bot.

## 📂 Estrutura

```
tests/
├── agent/              # Testes do comportamento do agente
│   ├── test_model_selection.py    # Heurística Haiku vs Sonnet
│   └── test_agent_responses.py    # (futuro) Testes de respostas
│
└── tools/              # Testes de tools individuais
    ├── test_proposal_tools.py     # (futuro) YAML operations
    ├── test_pdf_generation.py     # (futuro) PDF generation
    └── test_git_operations.py     # (futuro) Git commit/push
```

## 🧪 Testes Atuais

### `agent/test_model_selection.py`

Testa a heurística "Haiku First, Sonnet for Polish":
- ✅ Valida que operações normais usam Haiku
- ✅ Valida que polish/review usa Sonnet
- ✅ 100% de acurácia nos casos de teste

**Executar:**
```bash
python3 tests/agent/test_model_selection.py
```

## 🎯 Como Adicionar Novos Testes

### 1. Testes de Agent (comportamento geral)

```python
# tests/agent/test_agent_responses.py
import sys
sys.path.insert(0, '../..')

from agent.agent import get_agent_response

def test_basic_greeting():
    response = get_agent_response("Olá", session_id="test")
    assert "olá" in response.lower() or "oi" in response.lower()
```

### 2. Testes de Tools (funcionalidade específica)

```python
# tests/tools/test_proposal_tools.py
import sys
sys.path.insert(0, '../..')

from agent.tools import get_proposal_structure

def test_proposal_structure():
    structure = get_proposal_structure("docs/test/proposta.yml")
    assert "Seções" in structure
```

## 🚀 Executar Todos os Testes

```bash
# Executar teste específico
python3 tests/agent/test_model_selection.py

# Executar todos os testes (futuro - com pytest)
pytest tests/
```

## 📝 Boas Práticas

1. **Um arquivo por funcionalidade** testada
2. **Nomes descritivos**: `test_model_selection.py`, não `test1.py`
3. **Independência**: Cada teste deve rodar isoladamente
4. **Documentação**: Comentar o que cada teste valida
5. **Sem dependências externas**: Evitar chamar APIs reais (usar mocks)

## 🔮 Testes Futuros (Sugestões)

- [ ] `test_yaml_validation.py` - Validar YAML gerado
- [ ] `test_pdf_generation.py` - PDF gerado corretamente
- [ ] `test_cost_tracking.py` - Tracking de custos
- [ ] `test_session_persistence.py` - Redis persistence
- [ ] `test_error_handling.py` - Tratamento de erros
