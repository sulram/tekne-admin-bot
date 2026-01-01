# Como Usar a Tool de Edição Granular

## Nova Tool: `update_proposal_field`

Permite editar campos específicos do YAML sem reescrever o arquivo inteiro.

### Sintaxe

```python
update_proposal_field(
    yaml_file_path="docs/2026-01-cliente/proposta-projeto.yml",
    field_path="sections[1].bullets[0]",
    new_value="Novo valor aqui"
)
```

### Exemplos de Paths

| Path | O que edita |
|------|-------------|
| `meta.title` | Título da proposta |
| `meta.client` | Nome do cliente |
| `meta.date` | Data da proposta |
| `sections[0].title` | Título da primeira seção |
| `sections[1].content` | Conteúdo da segunda seção |
| `sections[0].bullets` | Lista completa de bullets |
| `sections[0].bullets[2]` | Terceiro bullet específico |
| `sections[2].subsections[0].name` | Nome da primeira subseção |

### Como Identificar nos Logs

Quando a tool for chamada, você verá nos logs:

```
2026-01-01 10:30:45 - agent.tools.proposal - INFO - 🎯 update_proposal_field called:
2026-01-01 10:30:45 - agent.tools.proposal - INFO -    File: docs/2026-01-coca-cola/proposta-vr-bubble-experience.yml
2026-01-01 10:30:45 - agent.tools.proposal - INFO -    Field: sections[1].bullets[1]
2026-01-01 10:30:45 - agent.tools.proposal - INFO -    New value type: str
```

E quando terminar com sucesso:

```
2026-01-01 10:30:46 - agent.tools.proposal - INFO - ✅ Successfully updated field in YAML:
2026-01-01 10:30:46 - agent.tools.proposal - INFO -    Path: sections[1].bullets[1]
2026-01-01 10:30:46 - agent.tools.proposal - INFO -    File: docs/2026-01-coca-cola/proposta-vr-bubble-experience.yml
```

### Quando o Agente Deve Usar

O agente deve escolher automaticamente entre:

1. **Edição Granular** (`update_proposal_field`) - Quando:
   - Usuário pede para "ajustar um bullet"
   - Usuário pede para "mudar o título da seção 2"
   - Usuário pede para "corrigir a data"
   - Mudanças pontuais e específicas

2. **Reescrita Completa** (`save_proposal_yaml`) - Quando:
   - Usuário pede "reformule toda a proposta"
   - Usuário pede "reescreva a seção X completamente"
   - Mudanças estruturais grandes

### Benefícios

- ✅ **Economia de tokens** - Não precisa carregar/reescrever YAML inteiro
- ✅ **Precisão** - Edita exatamente o campo solicitado
- ✅ **Rápido** - Navegação direta ao campo
- ✅ **Seguro** - Valida path antes de editar
