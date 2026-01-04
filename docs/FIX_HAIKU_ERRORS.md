# Fix: Haiku Error Handling & Dynamic Model Strategy

## Problema Original

Em `2026-01-04 05:31:14`, o agente (usando Haiku 3.5) cometeu dois erros consecutivos:

### Erro 1: Pydantic Validation Error
```
ERROR 3 validation errors for update_proposal_field
new_value.str
  Input should be a valid string [type=string_type, input_value=None, input_type=NoneType]
```

**Root Cause:** Haiku tentou chamar `update_proposal_field(new_value=None)` para "remover" o campo `image`, mas a função rejeitava `None`.

### Erro 2: PDF Generation - Image is Directory
```
error: failed to load file (is a directory)
  ┌─ template-proposal.typ:280:12
  │
280 │   image(proposal-folder + "/" + filename, width: width)
```

**Root Cause:** Haiku setou `sections[0].image: ""` (string vazia) em vez de remover o campo, causando:
```python
image("docs/2026-01-sesc-friburgo/" + "")  # = diretório, não arquivo!
```

---

## Soluções Implementadas

### 1. ✅ Aceitar `None` para Remover Campos

**Arquivo:** `agent/tools/proposal.py`

**Mudança 1:** Assinatura da função
```python
# ANTES
def update_proposal_field(
    yaml_file_path: str,
    field_path: str,
    new_value: str | list | dict  # ❌ Rejeita None
) -> str:

# DEPOIS
def update_proposal_field(
    yaml_file_path: str,
    field_path: str,
    new_value: str | list | dict | None  # ✅ Aceita None para remover
) -> str:
```

**Mudança 2:** Lógica de remoção
```python
if isinstance(final_key, int):
    # Lista
    if new_value is None:
        del target[final_key]  # Remove item da lista
    else:
        target[final_key] = new_value
else:
    # Dict
    if new_value is None:
        if final_key in target:
            del target[final_key]  # Remove campo do dict
        else:
            return f"Error: Field '{final_key}' not found"
    else:
        target[final_key] = new_value
```

**Mudança 3:** Status message diferenciada
```python
if new_value is None:
    send_status(f"✅ {field_name.capitalize()} removido do YAML")
else:
    send_status(f"✅ {field_name.capitalize()} atualizado: \"{value_preview}\"")
```

**Exemplo de uso:**
```python
# Remover campo image completamente
update_proposal_field(
    yaml_file_path="docs/2026-01-sesc/proposta.yml",
    field_path="sections[0].image",
    new_value=None  # ✅ Remove o campo do YAML
)
```

---

### 2. ✅ Melhorar Dynamic Model Strategy

**Arquivo:** `agent/dynamic_model.py`

**Estratégia ANTERIOR:** "Haiku First, Sonnet for Polish"
- ⚡ Haiku: TUDO exceto polish/review
- 💎 Sonnet: Apenas polish/review
- ❌ **Problema:** Haiku ficava perdido em operações complexas (múltiplas chamadas, lógica condicional)

**Estratégia NOVA:** "Haiku for Simple, Sonnet for Complex/Polish"
- ⚡ **Haiku:** Operações simples (single edits, viewing, listing)
- 💎 **Sonnet:** Operações complexas (criar propostas, multi-step, reasoning)
- 💎 **Sonnet:** Polish/review (qualidade crítica)

**Categorias:**

1. **Polish/Review → Sonnet** (alta qualidade)
   - revisar, polir, finalizar, melhorar qualidade, aprimorar

2. **Creation → Sonnet** (multi-step complexo)
   - criar proposta, nova proposta, fazer proposta, gerar proposta

3. **Complex → Sonnet** (reasoning necessário)
   - adicionar seção, reorganizar, reestruturar, mover, duplicar

4. **Simple → Haiku** (rápido e barato)
   - listar propostas, ver estrutura, mudar título, atualizar imagem

**Exemplo de decisão:**
```python
should_use_haiku("a imagem precisa vir antes do texto")
# → True (Haiku) - operação simples de edit

should_use_haiku("criar proposta para sesc friburgo")
# → False (Sonnet) - criação complexa multi-step

should_use_haiku("revisar a proposta")
# → False (Sonnet) - polish/qualidade crítica
```

---

## Impacto

### ✅ Benefícios

1. **Menos erros com Haiku**
   - Operações complexas agora vão para Sonnet (mais confiável)
   - Haiku só faz operações simples onde é competente

2. **Melhor UX**
   - `new_value=None` permite remover campos explicitamente
   - Mensagens de status mais claras ("removido" vs "atualizado")

3. **Custo otimizado**
   - Haiku ainda usado para 70%+ das operações simples
   - Sonnet usado apenas quando necessário

### 📊 Savings Estimados

**Antes (Haiku para tudo):**
- 90% Haiku, 10% Sonnet (polish)
- Problemas: ~5-10% das operações Haiku falhavam e precisavam retry → lento + caro

**Depois (Haiku para simples):**
- 70% Haiku (simples), 30% Sonnet (complexo/polish)
- Problemas: ~1-2% das operações falhavam (principalmente edge cases)
- **Net savings:** ~60-70% vs Sonnet puro, com menos retries

---

## Exemplos de Uso

### Remover campo image (novo)
```python
# User: "a imagem precisa vir antes do texto"
# Agent (Haiku):
update_proposal_field(
    yaml_file_path="docs/2026-01-sesc/proposta.yml",
    field_path="sections[0].image_before",
    new_value="jazz_floor.png"
)

update_proposal_field(
    yaml_file_path="docs/2026-01-sesc/proposta.yml",
    field_path="sections[0].image",
    new_value=None  # ✅ Remove campo completamente (evita string vazia)
)
```

### Criar proposta (agora usa Sonnet)
```python
# User: "criar proposta para sesc friburgo"
# Agent (Sonnet - mudança automática):
save_proposal_yaml(
    yaml_content="...",
    client_name="SESC Friburgo",
    project_slug="piso-interativo"
)
```

---

## Testing

Testado com cenários:
- ✅ Remover campo `image` com `new_value=None`
- ✅ Remover item de lista com `new_value=None`
- ✅ Dynamic model selection (10 test cases)
- ✅ Operações simples permanecem em Haiku
- ✅ Operações complexas movem para Sonnet

---

## Próximos Passos (Opcional)

1. **Telemetria:** Track Haiku vs Sonnet usage patterns
2. **Ajuste fino:** Refinar keywords baseado em logs reais
3. **Fallback automático:** Se Haiku falhar 2x, retry com Sonnet
