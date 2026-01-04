# Estratégia "Haiku First, Sonnet for Polish"

## 🎯 Filosofia

**Haiku para tudo, Sonnet apenas para finalização.**

Esta estratégia maximiza economia enquanto garante qualidade máxima nos momentos críticos.

## 📊 Divisão de Responsabilidades

### ⚡ Haiku 3.5 (90%+ das operações)

**Usamos Haiku para:**
- ✅ Criar propostas (rascunhos de qualidade)
- ✅ Editar conteúdo (títulos, datas, seções)
- ✅ Listar e visualizar propostas
- ✅ Gerar PDFs
- ✅ Operações de git (commit, push)
- ✅ Deletar propostas
- ✅ Reestruturar propostas
- ✅ Melhorias gerais
- ✅ Responder perguntas

**Por quê?** Haiku é **perfeitamente capaz** de fazer tudo isso com boa qualidade. O custo é 75% menor que Sonnet.

### 💎 Sonnet 4.5 (apenas ~5-10% das operações)

**Usamos Sonnet APENAS para:**
- 🔍 **Revisar** proposta completa
- ✨ **Polir** redação antes de enviar ao cliente
- 🎯 **Finalizar** versão que será apresentada
- 📝 **Melhorar qualidade** da escrita
- 🔎 **Review** crítico antes de entregar
- 💎 **Aprimorar** proposta para versão final

**Por quê?** Sonnet é mais cuidadoso, refinado e atento a detalhes. Vale a pena o custo extra nos momentos críticos.

## 🔑 Keywords que Ativam Sonnet

```python
polish_keywords = [
    'revisar', 'revise', 'revisada',
    'polir', 'polish', 'polida',
    'bem pensada',
    'finalizar', 'finalize', 'finalizada',
    'versão final',
    'review',
    'melhorar a qualidade', 'melhorar redação',
    'aprimorar',
]
```

**Tudo o resto = Haiku** (default)

## 💰 Economia Esperada

### Cenário Real (1 semana de trabalho)

| Operação | Qtd | Antes (Sonnet) | Depois (Haiku) | Economia |
|----------|-----|----------------|----------------|----------|
| Criar proposta | 5 | $0.60 | $0.15 | **$0.45** |
| Editar campos | 20 | $0.56 | $0.14 | **$0.42** |
| Listar propostas | 15 | $0.45 | $0.11 | **$0.34** |
| Gerar PDFs | 10 | $0.20 | $0.05 | **$0.15** |
| Reestruturar | 3 | $0.54 | $0.13 | **$0.41** |
| **Revisar final** | 2 | $0.24 | $0.24 | $0.00 |
| **TOTAL** | 55 | **$2.59** | **$0.82** | **$1.77 (68%)** |

**Economia semanal**: ~$1.77
**Economia mensal**: ~$7.08
**Economia anual**: ~$85.00

## 🎨 Workflow Típico

### 1. Criação Iterativa (Haiku)
```
Usuário: "Criar proposta para SESC com orçamento 50k"
Bot: [Haiku] Cria rascunho de qualidade
Custo: ~$0.03

Usuário: "Editar seção 2, adicionar mais detalhes sobre cronograma"
Bot: [Haiku] Edita rapidamente
Custo: ~$0.01

Usuário: "Alterar valor para 45k e ajustar prazo"
Bot: [Haiku] Ajusta valores
Custo: ~$0.01
```

### 2. Finalização (Sonnet)
```
Usuário: "Revisar a proposta antes de enviar ao cliente"
Bot: [Sonnet] Review completo, melhora redação, ajusta tom
Custo: ~$0.12

Total: ~$0.17 (vs $0.60+ se tudo fosse Sonnet)
```

## 📈 Comparação: Antes vs Depois

### Antes (Heurística Complexa)
```python
# Tentava adivinhar complexidade de cada operação
if "criar proposta" → Sonnet ($$$)
if "editar" → Haiku ($)
if "listar" → Haiku ($)
# Muitas regras, difícil manter
```

**Problemas:**
- ❌ Complexo (muitas regras)
- ❌ Ambíguo ("criar proposta" sempre caro?)
- ❌ Conservador (default = Sonnet)

### Depois (Haiku First)
```python
# Simples: Haiku para tudo, Sonnet só para polish
if "revisar" or "polir" or "finalizar" → Sonnet (qualidade)
else → Haiku (rápido e barato)
```

**Vantagens:**
- ✅ **Simples** (poucas keywords)
- ✅ **Claro** (polish = Sonnet, resto = Haiku)
- ✅ **Econômico** (default = Haiku)
- ✅ **Natural** (workflow real: rascunho → polir)

## 🧪 Testes: 100% Acurácia

```bash
python3 test_dynamic_model.py
# Results: 22/22 correct (100.0%)
```

Todos os casos testados funcionam perfeitamente:
- ✅ Criação → Haiku
- ✅ Edição → Haiku
- ✅ Listagem → Haiku
- ✅ Revisão → Sonnet ✨
- ✅ Finalização → Sonnet ✨

## 🎯 Quando o Usuário Deve Usar Sonnet?

Educar o usuário a pedir **revisão** nos momentos certos:

### ✅ Bom uso de Sonnet (vale a pena)
```
"Revisar a proposta antes de enviar"
"Polir a redação para o cliente"
"Finalizar versão para apresentação"
"A proposta está bem pensada?"
```

### ❌ Desperdício de Sonnet (Haiku faz igual)
```
"Criar proposta"           → Haiku cria rascunho ótimo
"Editar valor"             → Haiku edita perfeitamente
"Adicionar seção"          → Haiku adiciona sem problemas
"Mudar título"             → Haiku muda rapidamente
```

## 🚀 Impacto no Negócio

### ROI Direto
- **Economia imediata**: 68% em custos de API
- **Velocidade**: Haiku responde mais rápido
- **Qualidade garantida**: Sonnet revisa antes de entregar

### Workflow Melhorado
1. **Iteração rápida** (Haiku) → baixo custo, alta velocidade
2. **Polish final** (Sonnet) → alta qualidade quando importa
3. **Melhor custo-benefício** → cliente paga menos, recebe qualidade

## 📝 Como Usar

### Para o Usuário (Telegram)
```
# Trabalho normal (rápido e barato)
"Criar proposta para cliente X"
"Editar seção Y"
"Adicionar informação Z"

# Quando estiver pronto para enviar ao cliente
"Revisar a proposta completa"  ← Ativa Sonnet!
```

### Para o Desenvolvedor
A estratégia é **automática**. O código detecta keywords de polish e troca para Sonnet.

```python
# Em agent/dynamic_model.py
def should_use_haiku(message: str) -> bool:
    if any(keyword in message for keyword in polish_keywords):
        return False  # Use Sonnet
    return True  # Use Haiku (default)
```

## 🎓 Lições Aprendidas

1. **Simplicidade vence**: Menos regras = mais fácil de manter
2. **Default importa**: Haiku default = economia massiva
3. **Confiança em Haiku**: Haiku 3.5 é muito capaz!
4. **Polish é diferente**: Revisão/finalização merece Sonnet
5. **Workflow natural**: Espelha como humanos trabalham (rascunho → polish)

## 🔮 Próximos Passos

### Possíveis Melhorias
1. **Métricas de qualidade**: Comparar output Haiku vs Sonnet
2. **A/B testing**: Testar se Sonnet realmente melhora em polish
3. **User feedback**: "Essa proposta precisa de revisão?" (sugestão proativa)
4. **Auto-polish**: Depois de N edições, sugerir polish automático

### Monitoramento
- Taxa de uso Haiku vs Sonnet (esperado: 90/10)
- Economia real vs projetada
- Feedback de usuários sobre qualidade
