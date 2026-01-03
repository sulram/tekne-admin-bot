# 🏗️ Tekne Admin Bot - Arquitetura de Agente Único

**Data:** 2026-01-03
**Status:** ✅ Implementado e funcionando (branch main)
**Modelo:** Claude Sonnet 4.5 com prompt caching

---

## 📋 Resumo Executivo

**Arquitetura:** Agente único inteligente com todas as ferramentas disponíveis.

**Por que agente único?**
- ✅ **Simplicidade:** 1 agente, 1 arquivo, sem overhead de delegação
- ✅ **Flexibilidade:** Agente decide internamente qual abordagem usar
- ✅ **Cache funciona melhor:** Prompt caching economiza 90% após primeira mensagem
- ✅ **Baixo volume:** ~50 requests/mês não justifica complexidade de Team
- ✅ **Contexto compartilhado:** Todas as tarefas precisam do mesmo conhecimento de propostas

**Decisão baseada em análise:**
```
Team (3 agentes):
  Custo por request: $0.004-$0.055
  Overhead: Leader LLM call + delegação
  Complexidade: 3 agentes, routing, debugging difícil
  ROI: 278 anos para recuperar tempo de desenvolvimento

Agente único (Sonnet 4.5 + cache):
  Request 1: $0.054
  Request 2-N (cache): $0.010 (82% economia!)
  Simplicidade: 1 agente, decisão interna
  ROI: Imediato
```

---

## 🤖 Agente Único com Todas as Capacidades

### Arquitetura

```
┌─────────────────────────────────────────────────┐
│       PROPOSAL AGENT (Claude Sonnet 4.5)        │
│                                                  │
│  • Prompt caching (90% desconto após 1ª msg)   │
│  • Extended cache TTL (1 hora)                  │
│  • Histórico de 5 conversas                     │
│  • Session-aware (contexto por projeto)         │
└─────────────────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
   ┌────────┐   ┌─────────┐   ┌──────────┐
   │ CREATE │   │  EDIT   │   │  ADMIN   │
   │        │   │         │   │          │
   │ Gerar  │   │ Rápido  │   │ Listar   │
   │ Nova   │   │ ou      │   │ Deletar  │
   │ YAML   │   │ Complexo│   │ Cleanup  │
   └────────┘   └─────────┘   └──────────┘
```

**Características:**
- **Modelo:** Claude Sonnet 4.5 (qualidade > economia marginal)
- **Cache:** System prompt cacheado (90% economia após 1ª mensagem)
- **Decisão interna:** Agente escolhe tool certa baseado no contexto
- **Session-aware:** Vincula sessão ao projeto ativo

---

## 🛠️ Ferramentas Disponíveis

### 1. Criação e Estrutura
- `save_proposal_yaml()` - Salvar YAML completo (novas propostas)
- `load_proposal_yaml()` - Carregar proposta para análise/reestruturação
- `get_proposal_structure()` - Ver estrutura sem carregar YAML completo
- `read_section_content()` - Ler seção específica (economia de tokens)

### 2. Edição
- `update_proposal_field()` - Edições atômicas (preço, data, nome)
- Agente decide: usar `update_proposal_field` (rápido) ou `load + save` (complexo)

### 3. Administrativas
- `list_existing_proposals_tool()` - Listar todas as propostas
- `delete_proposal()` - Deletar proposta completa

### 4. Imagens
- `generate_image_dalle()` - Gerar mockups com DALL-E
- `wait_for_user_image()` - Aguardar upload do usuário
- `add_user_image_to_yaml()` - Adicionar imagem ao YAML

### 5. Output
- `generate_pdf_from_yaml_tool()` - Gerar PDF da proposta
- `commit_and_push_submodule()` - Commit no git

---

## 🆕 Novas Ferramentas (Planejadas)

### 1. Session Management

#### `set_active_project_session()`

**Objetivo:** Vincular sessão do usuário a um projeto específico

**Uso:**
```python
# Quando usuário cria nova proposta
User: "nova proposta de metaverso para o SESC"
Agent:
  1. Extrai cliente="SESC", projeto="metaverso"
  2. Chama set_active_project_session(client="SESC", project="metaverso")
  3. Retorna: "✅ Sessão vinculada ao projeto: 2026-01-sesc-metaverso"

# Quando usuário escolhe proposta existente
User: "editar a proposta da Coca-Cola"
Agent:
  1. list_existing_proposals_tool() → encontra "2025-12-cocacola-campanha"
  2. set_active_project_session(project_slug="2025-12-cocacola-campanha")
  3. Retorna: "✅ Trabalhando em: Coca-Cola - Campanha"
```

**Implementação:**
```python
from agno.tool import tool

@tool
def set_active_project_session(
    client: str = None,
    project: str = None,
    project_slug: str = None
) -> str:
    """
    Vincula a sessão do usuário a um projeto específico.

    Deve ser chamada:
    - Ao criar nova proposta (passar client + project)
    - Ao editar proposta existente (passar project_slug)

    Args:
        client: Nome do cliente (para novas propostas)
        project: Nome do projeto (para novas propostas)
        project_slug: Slug completo (para propostas existentes, ex: "2026-01-sesc-metaverso")

    Returns:
        Confirmação com slug do projeto ativo
    """
    # Gerar ou validar project_slug
    if project_slug is None:
        from datetime import datetime
        from agent.tools.proposal import slugify

        year_month = datetime.now().strftime("%Y-%m")
        client_slug = slugify(client)
        project_slug_name = slugify(project)
        project_slug = f"{year_month}-{client_slug}-{project_slug_name}"

    # Armazenar no session state (via RunContext no futuro)
    # Por enquanto: retornar slug para agente armazenar em memória

    return f"✅ Sessão vinculada ao projeto: {project_slug}"
```

**Benefícios:**
- ✅ Contexto isolado por projeto (economia de tokens)
- ✅ Histórico separado (debug mais fácil)
- ✅ Ferramentas sabem projeto ativo (não precisa passar toda vez)
- ✅ Preparação para multi-projeto simultâneo

---

### 2. Cleanup e Manutenção

#### `cleanup_orphaned_files()`

**Objetivo:** Remover PDFs e imagens órfãos (sem YAML correspondente)

**Triggers:**
- Manual: usuário pede "limpar arquivos órfãos"
- Automático (futuro): após deletar proposta, renomear projeto

**Lógica:**
```python
@tool
def cleanup_orphaned_files(dry_run: bool = True) -> str:
    """
    Remove PDFs e imagens órfãos do repositório.

    SEMPRE faça dry_run=True primeiro para mostrar o que será deletado!

    Args:
        dry_run: Se True, apenas lista arquivos (não deleta)

    Returns:
        Relatório de arquivos órfãos encontrados/removidos
    """
    docs_path = Path("submodules/tekne-proposals/docs")
    orphans = []

    # 1. PDFs órfãos (sem YAML correspondente)
    for pdf in docs_path.rglob("*.pdf"):
        yaml_name = pdf.stem + ".yml"  # ou proposta-{slug}.yml
        if not (pdf.parent / yaml_name).exists():
            orphans.append(("PDF órfão", pdf))

    # 2. Imagens órfãs (não referenciadas em nenhum YAML)
    all_yamls = list(docs_path.rglob("proposta-*.yml"))
    referenced_images = set()

    for yaml_path in all_yamls:
        yaml_content = yaml.safe_load(yaml_path.read_text())
        # Extrair imagens do YAML (capa, seções, etc)
        if 'capa' in yaml_content:
            referenced_images.add(yaml_content['capa'].get('imagem_fundo'))
        # ... extrair de outras seções

    for img in docs_path.rglob("images/*"):
        if img.name not in referenced_images:
            orphans.append(("Imagem órfã", img))

    # 3. Diretórios vazios
    for dir_path in docs_path.iterdir():
        if dir_path.is_dir() and not any(dir_path.iterdir()):
            orphans.append(("Diretório vazio", dir_path))

    if dry_run:
        report = f"🔍 Órfãos encontrados ({len(orphans)}):\n"
        for typ, path in orphans:
            report += f"  • {typ}: {path.relative_to(docs_path)}\n"
        report += f"\n⚠️ Use dry_run=False para confirmar remoção"
        return report
    else:
        for typ, path in orphans:
            path.unlink() if path.is_file() else path.rmdir()
        return f"✅ {len(orphans)} arquivos removidos"
```

**Exemplo de uso:**
```
User: "limpar arquivos órfãos"
Agent:
  1. cleanup_orphaned_files(dry_run=True)
  2. Mostra lista ao usuário
  3. Pergunta: "Confirma remoção?"
  4. cleanup_orphaned_files(dry_run=False)
```

---

#### `rename_proposal_directory()`

**Objetivo:** Renomear diretório quando cliente/projeto/data mudam

**Triggers automáticos:**
- Após `update_proposal_field()` alterar cliente, projeto ou data_envio
- Agente detecta mudança e chama automaticamente

**Lógica:**
```python
@tool
def rename_proposal_directory(
    current_slug: str,
    new_client: str = None,
    new_project: str = None,
    new_date: str = None
) -> str:
    """
    Renomeia diretório da proposta mantendo nomenclatura yyyy-mm-client-project.

    SEMPRE chamado automaticamente após editar cliente/projeto/data!

    Args:
        current_slug: Slug atual (ex: "2026-01-sesc-metaverso")
        new_client: Novo nome do cliente (se mudou)
        new_project: Novo nome do projeto (se mudou)
        new_date: Nova data no formato "YYYY-MM-DD" (se mudou)

    Returns:
        Confirmação com novo slug
    """
    docs_path = Path("submodules/tekne-proposals/docs")
    old_dir = docs_path / current_slug

    if not old_dir.exists():
        return f"❌ Diretório não encontrado: {current_slug}"

    # Parse slug atual
    parts = current_slug.split('-', 2)  # ['2026', '01', 'sesc-metaverso']
    year_month = f"{parts[0]}-{parts[1]}"

    # Carregar YAML para pegar valores atuais
    yaml_file = next(old_dir.glob("proposta-*.yml"))
    yaml_data = yaml.safe_load(yaml_file.read_text())

    # Determinar novos valores
    final_client = new_client or yaml_data['cliente']
    final_project = new_project or yaml_data['projeto']

    if new_date:
        from datetime import datetime
        date_obj = datetime.strptime(new_date, "%Y-%m-%d")
        year_month = date_obj.strftime("%Y-%m")

    # Gerar novo slug
    client_slug = slugify(final_client)
    project_slug = slugify(final_project)
    new_slug = f"{year_month}-{client_slug}-{project_slug}"

    if new_slug == current_slug:
        return f"ℹ️ Nenhuma mudança necessária"

    # Renomear diretório
    new_dir = docs_path / new_slug
    if new_dir.exists():
        return f"❌ Conflito: {new_slug} já existe"

    old_dir.rename(new_dir)

    # Renomear YAML também
    old_yaml = new_dir / yaml_file.name
    new_yaml_name = f"proposta-{client_slug}-{project_slug}.yml"
    old_yaml.rename(new_dir / new_yaml_name)

    # Atualizar session ativa
    # set_active_project_session(project_slug=new_slug)

    return f"✅ Renomeado:\n  De: {current_slug}\n  Para: {new_slug}"
```

**Workflow automático:**
```python
# Dentro de update_proposal_field() ou save_proposal_yaml():

# Após salvar YAML
if field in ['cliente', 'projeto', 'data_envio']:
    # Extrair slug atual da sessão ou do path
    current_slug = extract_slug_from_path(yaml_path)

    # Chamar rename automaticamente
    result = rename_proposal_directory(
        current_slug=current_slug,
        new_client=new_value if field == 'cliente' else None,
        new_project=new_value if field == 'projeto' else None,
        new_date=new_value if field == 'data_envio' else None,
    )

    logger.info(f"🔄 Auto-rename: {result}")
```

---

#### `validate_proposal_structure()`

**Objetivo:** Verificar integridade de proposta (YAML, imagens, nomenclatura)

**Uso:** Manual (usuário pede) ou automático antes de gerar PDF

**Lógica:**
```python
@tool
def validate_proposal_structure(project_slug: str) -> str:
    """
    Valida integridade de uma proposta.

    Verificações:
    1. YAML é válido (sintaxe)
    2. Campos obrigatórios presentes
    3. Imagens referenciadas existem
    4. Nomenclatura de diretório correta
    5. Nomenclatura de YAML correta

    Args:
        project_slug: Slug do projeto (ex: "2026-01-sesc-metaverso")

    Returns:
        Relatório de validação com erros/avisos
    """
    docs_path = Path("submodules/tekne-proposals/docs")
    project_dir = docs_path / project_slug

    errors = []
    warnings = []

    # 1. YAML existe e é válido
    yaml_files = list(project_dir.glob("proposta-*.yml"))
    if not yaml_files:
        errors.append("❌ Nenhum YAML encontrado")
        return format_validation_report(errors, warnings)

    yaml_path = yaml_files[0]
    try:
        yaml_data = yaml.safe_load(yaml_path.read_text())
    except Exception as e:
        errors.append(f"❌ YAML inválido: {e}")
        return format_validation_report(errors, warnings)

    # 2. Campos obrigatórios
    required_fields = ['cliente', 'projeto', 'data_envio', 'sections']
    for field in required_fields:
        if field not in yaml_data:
            errors.append(f"❌ Campo obrigatório ausente: {field}")

    # 3. Imagens referenciadas existem
    if 'capa' in yaml_data and 'imagem_fundo' in yaml_data['capa']:
        img_path = project_dir / yaml_data['capa']['imagem_fundo']
        if not img_path.exists():
            warnings.append(f"⚠️ Imagem não encontrada: {yaml_data['capa']['imagem_fundo']}")

    # 4. Nomenclatura de diretório
    # Validar formato yyyy-mm-client-project
    import re
    if not re.match(r'^\d{4}-\d{2}-[a-z0-9]+-[a-z0-9-]+$', project_slug):
        warnings.append(f"⚠️ Nomenclatura de diretório não segue padrão: {project_slug}")

    # 5. Nomenclatura de YAML
    expected_yaml = f"proposta-{slugify(yaml_data['cliente'])}-{slugify(yaml_data['projeto'])}.yml"
    if yaml_path.name != expected_yaml:
        warnings.append(f"⚠️ YAML deveria se chamar: {expected_yaml}")

    # 6. PDF órfão
    pdf_files = list(project_dir.glob("*.pdf"))
    if pdf_files:
        warnings.append(f"ℹ️ PDF temporário encontrado (pode ser removido)")

    return format_validation_report(errors, warnings)


def format_validation_report(errors, warnings):
    status = "✅ OK" if not errors else "❌ ERROS"
    if warnings and not errors:
        status = "⚠️ AVISOS"

    report = f"**Status:** {status}\n\n"

    if errors:
        report += "**Erros:**\n"
        for err in errors:
            report += f"  {err}\n"

    if warnings:
        report += "\n**Avisos:**\n"
        for warn in warnings:
            report += f"  {warn}\n"

    return report
```

---

## 🗂️ Sistema de Session ID Inteligente

### Formato Atual (Main)
```
{telegram_user_id}:default
```

### Formato Novo (Com Session Management)
```
{telegram_user_id}:{project_slug}
```

### Exemplos
```
# Antes (sessão global por usuário)
27463101:default

# Depois (sessão por projeto)
27463101:2026-01-sesc-metaverso
27463101:2026-01-coca-cola-campanha
27463101:2025-12-tekne-website
```

### Benefícios

1. **Isolamento de contexto**
   - Histórico de conversa específico do projeto
   - Não mistura "editar seção 2" entre projetos diferentes

2. **Economia de tokens**
   - Cache de prompt + histórico relevante apenas daquele projeto
   - Reduz contexto desnecessário

3. **Rastreabilidade**
   ```
   Session: 27463101:2026-01-sesc-metaverso
   Directory: submodules/tekne-proposals/docs/2026-01-sesc-metaverso/
   YAML: proposta-sesc-metaverso.yml
   ```

4. **Multi-projeto simultâneo** (futuro)
   - Usuário pode trabalhar em múltiplos projetos
   - Cada um com histórico separado

### Implementação

#### 1. Modificar `main.py` para aceitar session dinâmico

```python
# main.py
def handle_message(user_id: str, message: str, current_session: str = None):
    """
    Args:
        current_session: Session slug atual (ex: "2026-01-sesc-metaverso")
                        Se None, usa "default"
    """
    session_id = f"{user_id}:{current_session or 'default'}"

    response = get_agent_response(message, session_id=session_id)

    return response
```

#### 2. Adicionar comando para trocar projeto

```python
# Comando /projeto no Telegram
/projeto sesc-metaverso

# Ou implícito ao editar
User: "editar a proposta da Coca-Cola"
Agent:
  1. list_existing_proposals() → encontra slug
  2. Seta session automaticamente
  3. Retorna: "✅ Trabalhando em: 2025-12-coca-cola-campanha"
```

#### 3. Armazenar session ativa no estado do bot

```python
# core/session_manager.py (novo arquivo)
from threading import local

_thread_local = local()

def set_active_project(user_id: str, project_slug: str):
    """Armazena projeto ativo por usuário"""
    if not hasattr(_thread_local, 'user_projects'):
        _thread_local.user_projects = {}
    _thread_local.user_projects[user_id] = project_slug

def get_active_project(user_id: str) -> str:
    """Recupera projeto ativo do usuário"""
    if not hasattr(_thread_local, 'user_projects'):
        return "default"
    return _thread_local.user_projects.get(user_id, "default")
```

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

### Regras

1. **Diretório:** `yyyy-mm-client-projectslug`
   - Permite múltiplos projetos/mês por cliente
   - Slug = lowercase, sem acentos, hífens ao invés de espaços
   - Exemplo: `2026-01-sesc-oficinametaverso`

2. **YAML:** `proposta-{client-projectslug}.yml`
   - Sempre comitado no git
   - Permite buscar: `find . -name "proposta-*"`
   - Exemplo: `proposta-sesc-oficinametaverso.yml`

3. **PDF:** `yyyy-mm-client-projectslug.pdf`
   - **Temporário** (gitignored)
   - Gerado sob demanda
   - Enviado ao Telegram
   - Exemplo: `2026-01-sesc-oficinametaverso.pdf`

4. **Imagens:** `images/*.{png,jpg,webp}`
   - Comitadas no git
   - Referenciadas no YAML
   - Exemplo: `images/mockup-vr.png`

### Renomeação Automática

**Quando acontece:**
- Usuário muda campo `cliente` no YAML
- Usuário muda campo `projeto` no YAML
- Usuário muda campo `data_envio` (afeta ano-mês)

**O que é renomeado:**
1. Diretório do projeto
2. Arquivo YAML
3. Session ID do usuário

**Exemplo:**
```
# Estado inicial
Diretório: 2025-12-cliente-antigo/
YAML: proposta-cliente-antigo.yml
Session: 27463101:2025-12-cliente-antigo

# Usuário edita
update_proposal_field(field="cliente", value="SESC")
update_proposal_field(field="projeto", value="Metaverso")
update_proposal_field(field="data_envio", value="2026-01-15")

# Após renomeação automática
Diretório: 2026-01-sesc-metaverso/
YAML: proposta-sesc-metaverso.yml
Session: 27463101:2026-01-sesc-metaverso
```

---

## 🔄 Workflows Principais

### 1. Criar Nova Proposta

```
User: "nova proposta de metaverso para o SESC"
  ↓
Agent:
  1. Extrai: cliente="SESC", projeto="metaverso"
  2. set_active_project_session(client="SESC", project="metaverso")
     → session_id = "27463101:2026-01-sesc-metaverso"
  3. Coleta informações do usuário (se necessário)
  4. save_proposal_yaml(yaml_content, filename)
  5. generate_pdf_from_yaml_tool()
  6. commit_and_push_submodule()
  ↓
User: Recebe PDF no Telegram
```

### 2. Editar Proposta Existente

```
User: "editar a proposta da Coca-Cola"
  ↓
Agent:
  1. list_existing_proposals_tool()
     → encontra "2025-12-coca-cola-campanha"
  2. set_active_project_session(project_slug="2025-12-coca-cola-campanha")
  3. Responde: "✅ Trabalhando em: Coca-Cola - Campanha. O que deseja mudar?"
  ↓
User: "mudar a data para 8 de janeiro de 2026"
  ↓
Agent:
  1. get_proposal_structure()
  2. update_proposal_field(field="data_envio", value="2026-01-08")
  3. rename_proposal_directory() é chamado automaticamente
     → "2025-12-coca-cola-campanha" → "2026-01-coca-cola-campanha"
  4. generate_pdf_from_yaml_tool()
  5. commit_and_push_submodule()
  ↓
User: Recebe PDF atualizado
```

### 3. Limpeza de Órfãos

```
User: "limpar arquivos órfãos"
  ↓
Agent:
  1. cleanup_orphaned_files(dry_run=True)
  2. Mostra lista:
     "🔍 Órfãos encontrados (3):
       • PDF órfão: 2025-11-antigo.pdf
       • Imagem órfã: images/teste.png
       • Diretório vazio: rascunho/"
  3. Pergunta: "Confirma remoção?"
  ↓
User: "sim"
  ↓
Agent:
  1. cleanup_orphaned_files(dry_run=False)
  2. Responde: "✅ 3 arquivos removidos"
```

### 4. Validação de Proposta

```
User: "validar proposta"
  ↓
Agent:
  1. validate_proposal_structure(project_slug=current_session)
  2. Retorna relatório:
     "**Status:** ⚠️ AVISOS

     **Avisos:**
       ⚠️ Imagem não encontrada: images/mockup.png
       ℹ️ PDF temporário encontrado (pode ser removido)"
```

---

## 💰 Economia com Prompt Caching

### Cenário Real

**Request 1 (nova proposta):**
```
System prompt: 8000 tokens (CLAUDE.md + instruções)
User message: 500 tokens
History: 0 tokens
Total input: 8500 tokens

Custo input: 8500 × $3/1M = $0.0255
Cache write: 8000 × $6/1M = $0.048 (2x por criar cache)
Output: 2000 tokens × $15/1M = $0.030
Total: $0.1035
```

**Request 2-N (edições, mesmo projeto, próxima 1h):**
```
System prompt: 8000 tokens CACHED (90% desconto!)
User message: 500 tokens
History: 2000 tokens (última conversa)
Total input: 10500 tokens

Custo input (cache): 8000 × $0.3/1M = $0.0024 (cached!)
Custo input (novo): 2500 × $3/1M = $0.0075
Output: 500 tokens × $15/1M = $0.0075
Total: $0.0174 (83% economia!)
```

**Economia por sessão:**
- Request 1: $0.1035
- Requests 2-10: 9 × $0.0174 = $0.1566
- Total sessão: $0.26 para 10 requests

**Vs sem cache:**
- 10 × $0.1035 = $1.035
- **Economia: 75% ($0.775)**

---

## 🚧 Implementação Gradual

### Fase 1: Session Management (Alta Prioridade) ✅ FAZER AGORA

- [ ] Criar `set_active_project_session()` tool
- [ ] Modificar `main.py` para aceitar session dinâmico
- [ ] Criar `core/session_manager.py` para rastrear projeto ativo
- [ ] Testar vinculação automática ao criar/editar proposta

### Fase 2: Renomeação Automática (Alta Prioridade)

- [ ] Criar `rename_proposal_directory()` tool
- [ ] Integrar com `update_proposal_field()` e `save_proposal_yaml()`
- [ ] Detectar mudanças em cliente/projeto/data
- [ ] Atualizar session automaticamente após rename
- [ ] Testar workflow completo

### Fase 3: Cleanup (Média Prioridade)

- [ ] Criar `cleanup_orphaned_files()` tool
- [ ] Implementar detecção de PDFs órfãos
- [ ] Implementar detecção de imagens órfãs
- [ ] Implementar detecção de diretórios vazios
- [ ] Adicionar modo dry_run obrigatório
- [ ] Testar com repositório real

### Fase 4: Validação (Baixa Prioridade)

- [ ] Criar `validate_proposal_structure()` tool
- [ ] Validar sintaxe YAML
- [ ] Validar campos obrigatórios
- [ ] Validar existência de imagens
- [ ] Validar nomenclatura (diretório + YAML)
- [ ] Integrar com geração de PDF (validar antes)

---

## 📊 Métricas e Monitoramento

### Já Implementado (Main)

- ✅ Token usage por request (input + output)
- ✅ Cache hits (read tokens)
- ✅ Cache writes (creation tokens)
- ✅ Custo por request (detalhado)
- ✅ Custo acumulado (sessão + hoje + total)
- ✅ Tempo de resposta da API
- ✅ Tools usadas por request
- ✅ Avisos de commit faltando

### A Adicionar

- [ ] **Economia de cache por sessão** (calcular savings total)
- [ ] **Distribuição de tools** (qual tool é mais usada)
- [ ] **Sessões por projeto** (quantas conversas por proposta)
- [ ] **Taxa de renomeação** (quantas vezes rename automático acontece)
- [ ] **Órfãos removidos** (tracking de cleanup)

---

## 🎯 Decisões de Design

### Por Que Agente Único?

1. **Volume não justifica Team:**
   - ~50 requests/mês
   - ROI de Team seria 278 anos
   - Overhead > economia marginal

2. **Cache funciona melhor:**
   - System prompt cacheado 90% desconto
   - Funciona MUITO bem em conversas multi-turn
   - Economia real: 75% por sessão

3. **Contexto compartilhado:**
   - Todas as tarefas precisam entender estrutura YAML
   - Manager, CopyMaster, Reviewer teriam mesmo conhecimento
   - Delegação adiciona custo sem benefício

4. **Simplicidade = manutenibilidade:**
   - 1 agente, 1 arquivo
   - Debugging trivial
   - Logs diretos

### Por Que Session Por Projeto?

1. **Economia de tokens:**
   - Histórico relevante apenas daquele projeto
   - Cache de prompt + histórico específico

2. **UX melhor:**
   - "editar seção 2" não precisa especificar qual proposta
   - Contexto implícito

3. **Escalabilidade:**
   - Preparado para multi-projeto simultâneo
   - Cada projeto tem vida própria

### Por Que Renomeação Automática?

1. **Consistência:**
   - Nomenclatura sempre reflete conteúdo atual
   - Evita diretórios desatualizados

2. **DX melhor:**
   - Usuário não precisa lembrar de renomear
   - Agente cuida da organização

3. **Rastreabilidade:**
   - Session ID sincronizado com diretório
   - Git history limpo

---

## 📚 Referências

### Código Fonte (Main)

- `agent/agent.py` - Agente único
- `agent/tools/proposal.py` - Tools de proposta
- `agent/tools/pdf.py` - Geração de PDF
- `agent/tools/git.py` - Git operations
- `agent/tools/image.py` - DALL-E e upload
- `core/callbacks.py` - Status para Telegram
- `core/cost_tracking.py` - Tracking de custos
- `main.py` - Entry point (FastAPI + Telegram)

### Arquivos de Planning

- `ARCHITECTURE.md` (este arquivo) - Arquitetura completa
- `submodules/tekne-proposals/.claude/CLAUDE.md` - Schema YAML
- `submodules/tekne-proposals/.claude/skills/proposal-generator/skill.md` - Instruções detalhadas

---

**Última atualização:** 2026-01-03
**Versão:** 1.0 (Agente único + Session management + Cleanup)
**Status:** ✅ Main funcionando | 🔄 Novas features em planejamento
