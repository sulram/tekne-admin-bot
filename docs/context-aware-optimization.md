# Context-Aware Token Optimization

## O Dilema: Contexto vs Economia

### Problema Real:
Nem sempre podemos otimizar agressivamente. Algumas edições **precisam de contexto**:

```
❌ BAD: "Ajuste o segundo bullet para ficar mais alinhado com o primeiro"
         → Precisa LER ambos os bullets para entender o contexto!

✅ OK:  "Mude o título para 'Pop the Moment'"
         → Não precisa de contexto, é uma substituição direta
```

## 📊 Categorização de Edições

### Tipo 1: **Edições Cegas** (Context-Free)
**Pode usar otimização máxima** ✅

Exemplos:
- "Mude o título para X"
- "Atualize a data para 2026-02-01"
- "Troque o link para carolting.art"
- "Mude o cliente para 'Nike'"

**Estratégia**:
```python
# Não precisa carregar YAML inteiro
update_proposal_field(
    yaml_file_path="docs/2026-01-client/proposta.yml",
    field_path="meta.title",
    new_value="Pop the Moment"
)
# Input: ~300 tokens | Output: ~20 tokens
```

### Tipo 2: **Edições com Contexto Local** (Local Context)
**Precisa ler campo relacionado** ⚠️

Exemplos:
- "Ajuste o segundo bullet para combinar com o primeiro"
- "Mude o desconto para 20% e recalcule o total"
- "Atualize a bio do Marlus para mencionar o projeto anterior"

**Estratégia**:
```python
# Ler SOMENTE os campos necessários (não tudo!)
bullet1 = read_proposal_field("...", "sections[1].bullets[0]")  # 50 tokens
bullet2 = read_proposal_field("...", "sections[1].bullets[1]")  # 50 tokens

# Gerar novo bullet2 baseado em bullet1
# Atualizar
update_proposal_field("...", "sections[1].bullets[1]", new_bullet)

# Total: ~150 tokens vs 1,500 se carregasse tudo
```

### Tipo 3: **Edições com Contexto Global** (Global Context)
**Precisa entender estrutura completa** ⚠️⚠️

Exemplos:
- "Reformule a seção 2 para ter um tom similar à seção 1"
- "Adicione uma seção de timeline entre Technical Scope e Investment"
- "Revise todos os bullets para manter consistência de voz"

**Estratégia**:
```python
# Opção A: Carregar estrutura primeiro (leve)
structure = get_proposal_structure(...)  # ~200 tokens

# Se precisar de conteúdo completo:
# Opção B: Carregar tudo (sem otimização aqui)
full_yaml = load_proposal_yaml(...)  # ~1,200 tokens

# Mas pelo menos economiza no OUTPUT:
# Retornar só "✅ Reformulado" em vez do YAML todo
```

### Tipo 4: **Edições Iterativas** (Multi-Round)
**Usuário está refinando** 🔄

Exemplos:
```
User: "Ajuste o título"
Bot: "Sugestões: 1) Pop the Moment, 2) Bubble Rush, 3) Fizz & Joy"
User: "Gostei do 1"
Bot: [atualiza]
```

**Estratégia**:
```python
# Round 1: NÃO escrever ainda, só sugerir
# Input mínimo (estrutura ou campo específico)

# Round 2: Aplicar escolha
update_proposal_field("...", "meta.title", "Pop the Moment")
```

## 🧠 Sistema de Detecção Automática

Podemos ensinar o agente a detectar o tipo de edição:

```python
# No system prompt do agente:

"""
CONTEXT DETECTION for Edits:

1. **Direct replacement** (no context needed):
   - User provides exact new value
   - Examples: "change title to X", "update date to Y"
   - Action: Use update_proposal_field() directly
   - Cost: ~$0.002

2. **Local context** (related fields):
   - User references other nearby fields
   - Examples: "make bullet 2 match bullet 1", "recalculate total"
   - Action: Read only necessary fields, then update
   - Cost: ~$0.010

3. **Global context** (needs full picture):
   - User asks for consistency across sections
   - Examples: "reformulate to match tone", "add section between X and Y"
   - Action: Load full YAML (but minimal response)
   - Cost: ~$0.030

4. **Iterative refinement**:
   - User is exploring options
   - Examples: "suggest alternatives", "try different approaches"
   - Action: Don't write until user confirms
   - Cost: ~$0.005 per suggestion
"""
```

## 💡 Hybrid Approach (Best of Both Worlds)

### Smart Loading Function:

```python
@tool
def smart_edit_proposal(
    yaml_file_path: str,
    field_path: str,
    instruction: str,
    context_needed: bool = None  # Auto-detect if None
) -> str:
    """
    Intelligently choose between minimal and contextual editing.

    Args:
        yaml_file_path: Path to YAML
        field_path: Field to edit
        instruction: What to do (e.g., "make it more creative")
        context_needed: Force context loading (auto-detect if None)
    """

    # Auto-detect if context is needed
    if context_needed is None:
        context_keywords = [
            'match', 'similar', 'consistent', 'like',
            'align', 'compare', 'based on', 'referring to'
        ]
        context_needed = any(kw in instruction.lower() for kw in context_keywords)

    if context_needed:
        # Load related fields (not entire YAML)
        logger.info("🔍 Context needed - loading related fields")
        context = _load_related_context(yaml_file_path, field_path)
        return f"Context loaded: {context}. Now generate based on this."
    else:
        # Direct edit
        logger.info("⚡ Direct edit - no context needed")
        return f"Direct edit: {instruction}"


def _load_related_context(yaml_path: str, field_path: str) -> dict:
    """
    Load only contextually relevant fields.

    Examples:
    - If editing sections[2].bullets[0], load all bullets in sections[2]
    - If editing meta.title, load meta.subtitle too
    - If editing budget.total, load budget.subtotal and budget.discount
    """
    parts = parse_field_path(field_path)

    # Smart context rules
    if 'bullets' in field_path:
        # Load all bullets in that section
        section_idx = parts[parts.index('sections') + 1]
        return load_section_bullets(yaml_path, section_idx)

    elif 'budget' in field_path:
        # Load entire budget object
        return load_budget(yaml_path)

    elif 'meta' in field_path:
        # Load all meta fields (small anyway)
        return load_meta(yaml_path)

    else:
        # Default: load just that field
        return read_proposal_field(yaml_path, field_path)
```

## 📈 Cost Comparison by Edit Type

| Edit Type | Old Approach | Optimized | Smart Hybrid |
|-----------|--------------|-----------|--------------|
| Direct ("title=X") | $0.050 | $0.002 | **$0.002** ✅ |
| Local context | $0.050 | N/A ❌ | **$0.012** ✅ |
| Global context | $0.050 | N/A ❌ | **$0.035** ✅ |
| Iterative | $0.150 (3×) | N/A ❌ | **$0.020** ✅ |

## 🎯 Recommended Implementation

### Phase 1: Quick Wins (Now)
```python
# 1. Minimal responses for ALL edits
return "✅"  # Instead of full path

# 2. Structure tool for navigation
get_proposal_structure()  # Returns outline only
```
**Impact**: 50-70% savings with NO risk

### Phase 2: Smart Context Loading (Next)
```python
# 3. Auto-detect context needs
smart_edit_proposal(
    yaml_file="...",
    field_path="sections[1].bullets[0]",
    instruction="make it match the first bullet",
    context_needed=True  # Auto-detected!
)
```
**Impact**: 70-90% savings when context not needed, 30% when needed

### Phase 3: Advanced (Future)
```python
# 4. Incremental context loading
# Start minimal, load more only if needed
```

## 💭 Real Example

### Scenario: "Ajuste o segundo bullet para ficar mais criativo"

**Old approach**:
```python
# Load entire 4,800 char YAML
yaml = load_proposal_yaml(...)  # 1,200 tokens

# Agent sees everything, updates one bullet
save_proposal_yaml(...)  # 1,700 tokens output

# Total: 2,900 tokens = $0.09
```

**Smart hybrid**:
```python
# Detect: Needs creativity but maybe not other bullets?
# Ask user or peek at instruction

# Option A: No reference to other bullets
update_proposal_field(
    field_path="sections[1].bullets[1]",
    new_value="[Creative new bullet]"
)
# Total: 350 tokens = $0.012

# Option B: References like "align with first bullet"
bullets = read_section_bullets(section=1)  # 200 tokens
update_proposal_field(...)
# Total: 550 tokens = $0.018
```

**Savings**: 80-87% 🎉

## ✅ Conclusion

**Key Insight**: Não é "tudo ou nada". Use a abordagem certa para cada tipo de edição:

1. **Substituição direta** → Otimização máxima ⚡
2. **Contexto local** → Carregar só campos relacionados 🎯
3. **Contexto global** → Carregar tudo, mas resposta mínima 📦
4. **Iterativo** → Não escrever até confirmar 🔄

Quer implementar o **smart context detection**?
