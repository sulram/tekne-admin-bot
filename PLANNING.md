# 🚀 Tekne Admin Bot - Team Architecture (Final)

**Data:** 2026-01-03
**Status:** ✅ Implementado e funcionando
**Base:** Documentação oficial Agno v2 + código atual

---

## 📋 Resumo Executivo

**Objetivo:** Sistema multi-agente usando **Agno Team** com especialistas focados.

**Descobertas da documentação oficial Agno:**
- ✅ **Team cria um "team leader" interno automaticamente**
- ✅ **Team leader decide delegação baseado em `name`, `role`, `description` dos members**
- ✅ **Não existe leader customizado - apenas members especialistas**
- ✅ **Parametrização via `respond_directly`, `determine_input_for_members`, `delegate_to_all_members`**

**Arquitetura:**
```
┌─────────────────────────────────────────────────┐
│         TEAM (Agno Team com leader interno)     │
│  - Analisa input                                 │
│  - Decide delegação baseado em descriptions     │
│  - Sintetiza respostas dos members              │
└─────────────────────────────────────────────────┘
                      │
       ┌──────────────┼──────────────┐
       ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  MANAGER     │ │ COPYMASTER   │ │  REVIEWER    │
│ (Haiku 3.5)  │ │ (Sonnet 4.5) │ │ (Haiku 3.5)  │
│              │ │              │ │              │
│ Lista        │ │ Cria         │ │ Edita        │
│ Deleta       │ │ Proposta     │ │ Rápido       │
│ Consulta     │ │ Reestrutura  │ │ Atômico      │
└──────────────┘ └──────────────┘ └──────────────┘
```

**Importante:**
- ✅ Team tem leader **interno** (não customizável)
- ✅ Leader usa LLM para decidir delegação
- ✅ Decisão baseada em `description` + `role` dos members
- ❌ Não podemos dar tools customizadas ao leader interno

---

## 🤖 Agentes Especializados

### 1️⃣ Team Leader (Interno do Agno)

**Características:**
- Criado automaticamente pelo Team
- Usa modelo configurado no Team (ou herda default)
- Decide delegação via LLM baseado em descriptions
- Não tem acesso a tools customizadas

**Controle via parâmetros:**
```python
Team(
    members=[manager, copymaster, reviewer],
    respond_directly=True,            # ✅ Members respondem direto (sem síntese)
    determine_input_for_members=True, # Leader transforma input
    delegate_to_all_members=False,    # Delegação seletiva
)
```

---

### 2️⃣ MANAGER (Claude Haiku 3.5)

**Papel:** Especialista em Setup de Novos Projetos + Operações Administrativas (SEMPRE CHAMADO PRIMEIRO)

**Description (CRÍTICA para routing):**
```python
description="NEW PROJECT SETUP and administrative operations for proposal management. ALWAYS called first for new proposals to prepare session context. Specializes in: preparing new project context and session, identifying client/project info, listing proposals, viewing project structure, deleting proposals, cleanup tasks (orphaned PDFs/images, renaming directories/files), validating proposal structure, system queries."
```

**Keywords que atraem delegação:**
- **"nova", "criar", "começar", "iniciar" + "proposta"** → **PRIORIDADE MÁXIMA** (SEMPRE chamado primeiro)
- "listar", "mostrar", "ver", "quais"
- "deletar", "remover", "apagar"
- "quantas", "status", "info"
- "limpar", "cleanup", "órfãos"
- "renomear", "reorganizar diretórios"
- "validar", "verificar"

**Workflow de Coleta de Contexto:**
```
User: "proposta de metaverso!"
  ↓
Manager:
  1. identify_client_project() → client=None, project="metaverso"
  2. Pergunta: "Qual o cliente para essa proposta de metaverso?"
  ↓
User: "SESC"
  ↓
Manager (mantém histórico):
  1. identify_client_project() → client="SESC", project="metaverso"
  2. prepare_new_project_context() → session_id="2026-01-sesc-metaverso"
  3. Informa: "Pronto! Contexto definido: SESC - metaverso"
  ↓
Team Leader → CopyMaster (com contexto completo)
```

**Tools:**
```python
tools=[
    # Context & Routing
    identify_client_project,          # Identificar cliente/projeto
    prepare_new_project_context,      # Preparar paths e session

    # Information & Listing
    list_existing_proposals_tool,     # Listar propostas
    get_proposal_structure,           # Ver estrutura
    read_section_content,             # Ler seções (read-only)

    # Cleanup & Maintenance
    delete_proposal,                  # Deletar propostas
    cleanup_orphaned_files,           # PDFs e imagens órfãos
    rename_proposal_directory,        # Renomear diretórios
    rename_proposal_yaml,             # Renomear YAMLs
    validate_proposal_structure,      # Verificar integridade
]
```

**Responsabilidades de Cleanup:**
1. **PDFs órfãos:** Remover PDFs sem YAML correspondente
2. **Imagens órfãs:** Remover imagens não referenciadas em nenhum YAML
3. **Diretórios vazios:** Remover diretórios sem propostas
4. **Renomeação:** Manter nomenclatura consistente (yyyy-mm-client-project)
5. **Validação:** Verificar integridade de YAMLs e paths

**Benefícios:**
- ✅ **Custo mínimo:** Haiku 3.5 = $0.80/1M tokens (vs Sonnet $3.00/1M)
- ✅ **Velocidade:** Respostas rápidas para queries simples
- ✅ **Separação de responsabilidades:** Admin vs criativo/edição
- ✅ **Manutenção automática:** Cleanup do repositório
- ✅ **Escalável:** Futuro analytics, backups, métricas

**Proibições:**
- ❌ Não pode editar conteúdo de propostas (sem `save_proposal_yaml`, `update_proposal_field`)
- ❌ Não gera PDFs (apenas remove órfãos)
- ❌ Não faz commits de propostas (apenas cleanup commits se necessário)

---

### 3️⃣ COPYMASTER (Claude Sonnet 4.5)

**Papel:** Especialista em Geração de Conteúdo (Qualidade > Velocidade) - CHAMADO APÓS MANAGER

**Description (CRÍTICA para routing):**
```python
description="Finalizes proposal content with high quality writing. Called AFTER Manager provides complete briefing. Specializes in: writing final proposal from briefing, restructuring content, improving quality, enhancing persuasiveness."
```

**Keywords que atraem delegação:**
- **"finalizar"** → keyword principal (Manager passa a bola)
- "escrever", "redigir"
- "reestruturar", "reorganizar"
- "melhorar", "expandir"

**❌ Keywords REMOVIDAS (agora são do Manager):**
- ~~"criar"~~, ~~"nova proposta"~~ → Manager responsibility

**Workflow Sequencial:**
```
Manager → prepara briefing completo → "Pronto para CopyMaster finalizar"
Team Leader → detecta "finalizar" → delega para CopyMaster
CopyMaster → recebe briefing → gera proposta
```

**Tools:**
```python
tools=[
    save_proposal_yaml,        # Salvar YAML completo
    load_proposal_yaml,        # Carregar para reestruturação
    update_proposal_field,     # Edições pontuais também
    get_proposal_structure,
    read_section_content,
    generate_pdf_from_yaml_tool,
    generate_image_dalle,
    wait_for_user_image,
    add_user_image_to_yaml,
    commit_and_push_submodule,
    # delete_proposal removido - Manager handles this
]
```

**Cache Configuration:**
```python
model=Claude(
    id="claude-sonnet-4-5",
    cache_system_prompt=True,                    # ✅ Agno native
    extended_cache_time=True,                    # ✅ 1h TTL
    betas=["extended-cache-ttl-2025-04-11"],
)
```

---

### 4️⃣ REVIEWER (Claude Haiku 3.5)

**Papel:** Editor Rápido e Cirúrgico

**Description (CRÍTICA para routing):**
```python
description="Fast and surgical edits to existing proposals. Specializes in: fixing typos, updating pricing, changing dates, correcting names, quick edits, atomic changes, fast corrections."
```

**Keywords que atraem delegação:**
- "mudar", "alterar", "atualizar"
- "corrigir", "fixar"
- "editar" + campo específico
- "data", "preço", "nome"

**Tools:**
```python
tools=[
    update_proposal_field,     # FERRAMENTA PRINCIPAL
    get_proposal_structure,
    read_section_content,
    generate_pdf_from_yaml_tool,
    commit_and_push_submodule,
]
```

**Proibições:**
- ❌ Não tem `save_proposal_yaml` (apenas CopyMaster)
- ❌ Não carrega YAML completo (usa structure + section reads)

---

## ⚙️ Configuração do Team

### Código Real

```python
from agno.team import Team
from agent.team.copymaster import copymaster_agent
from agent.team.reviewer import reviewer_agent

proposal_team = Team(
    members=[copymaster_agent, reviewer_agent],  # Apenas specialists
    name="Proposal Team",
    description="Multi-agent system for managing commercial proposals with intelligent delegation",
    db=get_team_db(),  # RedisDb ou InMemoryDb

    # Delegation configuration (Agno v2)
    respond_directly=False,              # Leader sintetiza respostas
    determine_input_for_members=True,    # Leader transforma input
    delegate_to_all_members=False,       # Delegação seletiva

    # Logging & Debug
    store_member_responses=True,         # ✅ CRITICAL: Popula member_responses
    show_members_responses=False,        # Verbose logs off
    debug_mode=False,                    # Custom logging only
)
```

### Parâmetros Importantes

| Parâmetro | Valor | Significado |
|-----------|-------|-------------|
| `respond_directly` | `False` | Team leader sintetiza respostas dos members |
| `determine_input_for_members` | `True` | Team leader cria input customizado por member |
| `delegate_to_all_members` | `False` | Delegação seletiva (não broadcast) |
| `store_member_responses` | `True` | **CRÍTICO**: Armazena RunOutput de cada member |
| `show_members_responses` | `False` | Desabilita logs verbosos do Agno |
| `debug_mode` | `False` | Usamos logging customizado |

---

## 🔄 Como a Delegação Funciona

### Fluxo Real (baseado em docs)

```
User: "mudar a data da proposta Coca-Cola para 8 de janeiro"
  ↓
Team Leader (interno):
  1. Analisa mensagem
  2. Compara com descriptions dos members
  3. Identifica keywords: "mudar", "data" → match com Reviewer
  4. Chama tool delegate_task_to_member(member=Reviewer, task=...)
  ↓
Reviewer:
  - Recebe task do leader
  - Executa get_proposal_structure()
  - Executa update_proposal_field()
  - Retorna resultado
  ↓
Team Leader:
  - Sintetiza resposta do Reviewer
  - Retorna ao usuário
```

### Decisão do Leader

O team leader interno usa:
1. **`description`** de cada member (keywords)
2. **`role`** (papel geral)
3. **`name`** (identificação)
4. **LLM reasoning** para decidir melhor match

**Exemplo:**
```python
# Reviewer description
"Fast and surgical edits... updating pricing, changing dates, correcting names"

# User input
"mudar a data para 8 de janeiro"

# Leader reasoning
"mudar" + "data" → keywords match Reviewer description → delegate to Reviewer
```

---

## 🛠️ Tools e Responsabilidades

### CopyMaster Tools

| Tool | Uso |
|------|-----|
| `save_proposal_yaml` | ✅ Exclusivo - salvar YAML completo |
| `load_proposal_yaml` | ✅ Exclusivo - carregar para reestruturação |
| `update_proposal_field` | ✅ Compartilhado - edições pontuais |
| `generate_image_dalle` | ✅ Geração de mockups |
| `add_user_image_to_yaml` | ✅ Adicionar imagens |

### Reviewer Tools

| Tool | Uso |
|------|-----|
| `update_proposal_field` | ✅ PRINCIPAL - edições atômicas |
| `get_proposal_structure` | ✅ Ver estrutura sem carregar YAML |
| `read_section_content` | ✅ Ler seção específica |

### Tools Compartilhadas

| Tool | Ambos |
|------|-------|
| `generate_pdf_from_yaml_tool` | ✅ |
| `commit_and_push_submodule` | ✅ |

---

## 📊 Logging e Debugging

### Structure de member_responses

```python
response = proposal_team.run(message, session_id=session_id)

# response.member_responses é uma lista de RunOutput
for member_run in response.member_responses:
    agent_name = member_run.agent_name      # "CopyMaster" ou "Reviewer"
    content = member_run.content            # Resposta do member

    # Tools usadas
    if member_run.tools:
        for tool_exec in member_run.tools:
            tool_name = tool_exec.tool_name  # Nome da tool
            tool_args = tool_exec.tool_args  # Argumentos
            result = tool_exec.result        # Resultado
```

### Logging Customizado

```python
# agent/team/__init__.py
if hasattr(response, 'member_responses') and response.member_responses:
    for member_run in response.member_responses:
        if hasattr(member_run, 'agent_name'):
            agents_used.add(member_run.agent_name)
            logger.info(f"🔍 Member: {member_run.agent_name}")

            # Log response
            if hasattr(member_run, 'content'):
                logger.info(f"  ↳ Response: {str(member_run.content)[:150]}")

            # Log tools
            if hasattr(member_run, 'tools') and member_run.tools:
                for tool_exec in member_run.tools:
                    logger.info(f"  └─ Tool: {tool_exec.tool_name}")
            else:
                logger.warning(f"  ⚠️  {member_run.agent_name} didn't use any tools!")
```

---

## 🎯 Decisão CopyMaster vs Reviewer

### Princípio

**Leader interno decide baseado em keywords nas descriptions**

### Reviewer (keywords)
- "mudar", "alterar", "atualizar"
- "corrigir", "fixar"
- "data", "preço", "nome"
- "quick", "fast", "atomic"

### CopyMaster (keywords)
- "criar", "nova"
- "reestruturar", "reorganizar"
- "melhorar", "expandir"
- "mesclar", "dividir"
- "reescrever", "enhancing"

### Exemplos

| User Input | Member | Razão |
|------------|--------|-------|
| "mudar a data para 8 de janeiro" | Reviewer | "mudar" + "data" |
| "criar uma nova proposta" | CopyMaster | "criar" + "nova" |
| "melhorar o texto da seção 2" | CopyMaster | "melhorar" (creative) |
| "corrigir o nome do cliente" | Reviewer | "corrigir" + "nome" |
| "reestruturar as seções" | CopyMaster | "reestruturar" (structural) |
| "atualizar o preço para R$ 50k" | Reviewer | "atualizar" + "preço" |

---

## 💰 Estimativa de Custos

### Preços (Sonnet 4.5 + Haiku 3.5)

| Modelo | Input $/1M | Output $/1M |
|--------|-----------|-------------|
| Sonnet 4.5 | $3.00 | $15.00 |
| Haiku 3.5 | $0.80 | $4.00 |

### Cenários

**Edição simples (Reviewer):**
```
Team leader: 500 in + 100 out = $0.0009
Reviewer:    1500 in + 500 out = $0.0032
Total: ~$0.004 (95% economia vs agent único)
```

**Criação (CopyMaster):**
```
Team leader: 500 in + 200 out = $0.0012
CopyMaster:  8000 in + 2000 out = $0.054 (com cache: $0.027)
Total: ~$0.028-$0.055
```

**Economia média: ~58%**

---

## 🔧 Workflows com Agno

### Por Que Team em Vez de Workflow?

**Team (Atual):**
- ✅ **Uso:** Comandos ad-hoc do usuário (interface conversacional)
- ✅ **Vantagem:** Delegação inteligente baseada em intent
- ✅ **Exemplo:** "mudar data" → Reviewer, "melhorar seção" → CopyMaster

**Workflow (Futuro - Opcional):**
- ✅ **Uso:** Fluxos determinísticos e multi-step
- ✅ **Vantagem:** Performance, previsibilidade, cache melhor
- ✅ **Exemplo:** `/criar_proposta` sempre executa os mesmos steps

### Decisão Atual
- ✅ **Manter Team** para interface conversacional (Telegram)
- ➕ **Avaliar Workflows** para comandos estruturados (/criar, /review)
- 📊 **Métricas:** Testar performance antes de migrar

### Exemplo de Workflow (Futuro)

```python
# Para criação de proposta (determinístico)
from agno.workflow import Workflow, Step

create_workflow = Workflow(
    steps=[
        Step(name="identify", executor=identify_context),
        Step(name="create", agent=copymaster_agent),
        Step(name="pdf", executor=generate_pdf),
        Step(name="commit", executor=commit_git),
    ]
)

# Para comandos ad-hoc (delegação dinâmica) - mantemos Team:
proposal_team.run("mudar data")  # → Reviewer
proposal_team.run("melhorar seção")  # → CopyMaster
```

---

## 🛠️ Melhorias Futuras (Baseadas em Docs)

### 1. Tools com run_context

**Atual:**
```python
def save_proposal_yaml(yaml_content: str, filename: str) -> str:
    pass
```

**Melhoria:**
```python
from agno.run import RunContext

def save_proposal_yaml(
    run_context: RunContext,
    yaml_content: str,
    filename: str
) -> str:
    # Acessar session state
    session_state = run_context.session_state or {}
    client_name = session_state.get("current_client", "unknown")

    # Metadata útil
    metadata = run_context.metadata or {}
    logger.info(f"Saving proposal for {client_name}")

    # ... resto da implementação
```

**Benefícios:**
- ✅ Tools podem compartilhar contexto via session_state
- ✅ Não precisamos passar tudo via argumentos
- ✅ Mais limpo e extensível

### 2. Tool Hooks para Logging

```python
def log_tool_execution(function_name, function_call, arguments):
    start = time.time()
    logger.info(f"🔧 Tool: {function_name}")
    result = function_call(**arguments)
    logger.info(f"  ⏱️  {time.time() - start:.2f}s")
    return result

proposal_team = Team(
    members=[copymaster_agent, reviewer_agent],
    tool_hooks=[log_tool_execution],  # ← Novo
    ...
)
```

**Benefícios:**
- ✅ Monitoramento automático de todas as tools
- ✅ Timing sem modificar cada tool
- ✅ Validação centralizada

---

## 📁 Nomenclatura de Arquivos

### Estrutura Oficial

```
yyyy-mm-client-projectslug/
├── proposta-{client-projectslug}.yml          (git)
├── yyyy-mm-client-projectslug.pdf             (gitignored, temporário)
└── images/
    ├── mockup.png                             (git)
    └── diagram.png                            (git)
```

### Exemplos

```
2026-01-sesc-oficinametaverso/
├── proposta-sesc-oficinametaverso.yml
├── 2026-01-sesc-oficinametaverso.pdf
└── images/
    └── mockup-vr.png

2026-01-sesc-exposicao/
├── proposta-sesc-exposicao.yml
├── 2026-01-sesc-exposicao.pdf
└── images/
    ├── banner.png
    └── layout.png
```

### Regras

1. **Diretório:** `yyyy-mm-client-projectslug`
   - Permite múltiplos projetos/mês por cliente
   - Slug = lowercase, sem acentos, hífens ao invés de espaços

2. **YAML:** `proposta-{client-projectslug}.yml`
   - Sempre comitado no git
   - Permite buscar: `find . -name "proposta-*"`

3. **PDF:** `yyyy-mm-client-projectslug.pdf`
   - **Temporário** (gitignored)
   - Gerado sob demanda
   - Enviado ao Telegram

4. **Imagens:** `images/*.{png,jpg,webp}`
   - Comitadas no git
   - Referenciadas no YAML

---

## 🗂️ Sistema de Session ID

### Formato
```
{telegram_user_id}:{yyyy-mm-client-projectslug}
```

### Exemplos
```
27463101:2026-01-sesc-oficinametaverso
27463101:2026-01-sesc-exposicao
27463101:2025-12-tekne-website
27463101:default  # fallback
```

### Alinhamento com Nomenclatura

Session ID e diretório são **idênticos** (exceto user_id):
```
Session:    27463101:2026-01-sesc-oficinametaverso
Directory:           2026-01-sesc-oficinametaverso/
```

### Benefícios
1. **Isolamento de contexto** → cada projeto tem histórico separado
2. **Economia de tokens** → histórico relevante apenas daquele projeto
3. **Rastreabilidade** → fácil debug e analytics
4. **Alinhamento** → session_id ↔ diretório ↔ git

---

## 🧹 Cleanup Tools (Manager)

### 1. `cleanup_orphaned_files()`

**Objetivo:** Remover PDFs e imagens sem YAML correspondente

**Lógica:**
```python
1. Escanear submodules/tekne-proposals/docs/
2. Para cada PDF:
   - Verificar se existe YAML com mesmo nome base
   - Se não: adicionar à lista de órfãos
3. Para cada imagem em */images/:
   - Verificar se está referenciada em algum YAML
   - Se não: adicionar à lista de órfãos
4. Perguntar ao usuário antes de deletar
5. Remover arquivos confirmados
6. Retornar relatório
```

**Exemplo:**
```
Órfãos encontrados:
- 2025-12-cliente-antigo.pdf (sem YAML)
- docs/2026-01-sesc/images/teste.png (não referenciado)

Deletar? (3 arquivos, 2.5MB)
```

---

### 2. `rename_proposal_directory()`

**Objetivo:** Renomear diretório mantendo nomenclatura yyyy-mm-client-project

**Lógica:**
```python
1. Validar diretório atual existe
2. Gerar novo nome baseado em regras:
   - yyyy-mm do primeiro YAML no diretório
   - client-project extraído do YAML
3. Verificar se novo nome já existe
4. Mover diretório
5. Atualizar referências internas
6. Retornar confirmação
```

**Exemplo:**
```
Renomear:
  De: docs/projeto-sesc/
  Para: docs/2026-01-sesc-oficinametaverso/
```

---

### 3. `rename_proposal_yaml()`

**Objetivo:** Renomear YAML seguindo padrão proposta-{client-project}.yml

**Lógica:**
```python
1. Ler YAML atual
2. Extrair client e project do conteúdo
3. Gerar novo nome: proposta-{client-slug}-{project-slug}.yml
4. Verificar conflitos
5. Renomear arquivo
6. Atualizar git se necessário
7. Retornar confirmação
```

**Exemplo:**
```
Renomear:
  De: proposta-antiga.yml
  Para: proposta-sesc-oficinametaverso.yml
```

---

### 4. `validate_proposal_structure()`

**Objetivo:** Verificar integridade de propostas

**Checklist:**
```python
1. YAML válido (sintaxe)
2. Campos obrigatórios presentes
3. Imagens referenciadas existem
4. Nomenclatura de diretório correta
5. Nomenclatura de YAML correta
6. PDF órfão (opcional)
```

**Retorno:**
```yaml
validation_report:
  proposal: "docs/2026-01-sesc-oficinametaverso/proposta-sesc-oficinametaverso.yml"
  status: "warnings"
  errors: []
  warnings:
    - "PDF órfão detectado (pode ser removido)"
    - "Imagem 'mockup.png' referenciada mas não encontrada"
  suggestions:
    - "Considere gerar PDF atualizado"
```

---

## 🚧 Estado Atual da Implementação

### ✅ Completo

- [x] CopyMaster agent configurado
- [x] Reviewer agent configurado
- [x] Team com members corretos (sem leader customizado)
- [x] Parâmetros de delegação configurados
- [x] `store_member_responses=True` habilitado
- [x] Logging customizado de agents/tools
- [x] Cache de prompt (CopyMaster)
- [x] Arquivo `agent/team/leader.py` removido
- [x] Imports limpos em `agent/team/__init__.py`

### 🔄 Próximos Passos

#### 1. Manager Agent (Alta Prioridade)
- [ ] Criar `agent/team/manager.py` com Haiku 3.5
- [ ] Implementar cleanup tools:
  - [ ] `cleanup_orphaned_files()` - PDFs e imagens órfãos
  - [ ] `rename_proposal_directory()` - Renomear diretórios
  - [ ] `rename_proposal_yaml()` - Renomear YAMLs
  - [ ] `validate_proposal_structure()` - Verificar integridade
- [ ] Adicionar Manager ao Team em `agent/team/__init__.py`
- [ ] Mover routing tools (`identify_client_project`, `prepare_new_project_context`) para Manager
- [ ] Testar delegação do Team Leader → Manager

#### 2. Melhorias (Média Prioridade)
- [ ] Adicionar `run_context` às tools críticas
- [ ] Implementar tool hooks para logging automático
- [ ] Avaliar Workflows para fluxos específicos (/criar_proposta)
- [ ] CopyMaster também recebe routing tools (para criar com contexto)

#### 3. Otimizações (Baixa Prioridade)
- [ ] Documentar decisões de design
- [ ] Adicionar métricas de performance
- [ ] Testar cache hit rate
- [ ] Analytics de uso de agents (qual agent é mais chamado)

---

## 📚 Referências

### Documentação Oficial Agno

- `docs/agno-docs-basics-teams.txt` - Teams e delegação
- `docs/agno-docs-basics-workflows.txt` - Workflows determinísticos
- `docs/agno-docs-basics-tools.txt` - Tools e hooks

### Código Fonte

- `agent/team/__init__.py` - Team setup
- `agent/team/manager.py` - Manager agent (a criar)
- `agent/team/copymaster.py` - CopyMaster agent
- `agent/team/reviewer.py` - Reviewer agent
- `agent/tools/cleanup.py` - Cleanup tools (a criar)
- `agent/tools/routing.py` - Routing tools (existente)

---

**Última atualização:** 2026-01-03
**Versão:** 5.0 (Manager agent + cleanup tools)
**Status:** 🔄 Em planejamento - Manager agent
