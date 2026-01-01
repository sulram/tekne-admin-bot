"""
Tekne Proposal Generator Agent
Uses Agno with Claude to create commercial proposals following CLAUDE.md rules
"""

import os
import yaml
import subprocess
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, List
from agno.agent import Agent
from agno.models.anthropic import Claude
from agno.db.in_memory import InMemoryDb
from agno.tools import tool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Path to submodule
SUBMODULE_PATH = Path(__file__).parent / "submodules" / "tekne-proposals"
DOCS_PATH = SUBMODULE_PATH / "docs"
CLAUDE_MD_PATH = SUBMODULE_PATH / "CLAUDE.md"

# Global callback for sending status messages to user
_status_callback: Optional[Callable[[str], None]] = None

# Global callback for managing user session state
_session_state_callback: Optional[Callable[[str, dict], None]] = None

def set_status_callback(callback: Callable[[str], None]) -> None:
    """Set callback function to send status updates to user"""
    global _status_callback
    _status_callback = callback

def send_status(message: str) -> None:
    """Send status message to user if callback is set"""
    if _status_callback:
        _status_callback(message)

def set_session_state_callback(callback: Callable[[str, dict], None]) -> None:
    """Set callback function to update user session state"""
    global _session_state_callback
    _session_state_callback = callback

def update_session_state(session_id: str, state_updates: dict) -> None:
    """Update user session state if callback is set"""
    if _session_state_callback:
        _session_state_callback(session_id, state_updates)


def load_claude_instructions() -> str:
    """Load CLAUDE.md as agent instructions"""
    base_instructions = ""

    if CLAUDE_MD_PATH.exists():
        base_instructions = CLAUDE_MD_PATH.read_text()
        logger.info(f"Loaded CLAUDE.md instructions ({len(base_instructions)} chars)")
    else:
        base_instructions = "Generate proposals in YAML format for Tekne Studio."

    # Add bot-specific instructions
    bot_instructions = """

---

## WORKFLOW - CRITICAL

**MANDATORY STEPS after ANY YAML change:**
1. Save YAML using `save_proposal_yaml()` → returns file path
2. Generate PDF using `generate_pdf_from_yaml(yaml_path)`
3. **IMMEDIATELY** commit using `commit_and_push_submodule(message, files)`

**CRITICAL: How to call commit_and_push_submodule correctly:**
```python
# After save_proposal_yaml returns the path (e.g., "docs/2025-12-sesc/proposta-x.yml")
yaml_path = save_proposal_yaml(...)
generate_pdf_from_yaml(yaml_path)
commit_and_push_submodule(
    message="Update proposal for Client X",
    files=[yaml_path]  # MUST pass as a list!
)
```

**You MUST call `commit_and_push_submodule()` after EVERY proposal creation or edit.**
- ALWAYS provide both parameters: `message` AND `files`
- `files` parameter is a LIST containing the YAML file path
- Images are auto-detected and included automatically
- This is NOT optional - ALWAYS do this step

## LISTING & EDITING PROPOSALS

**Listing proposals:**
- `list_existing_proposals(limit)` returns most recent proposals (default: 10)
- Sorted by date (YYYY-MM prefix) in descending order

**Editing proposals:**
- User can request to edit by number (from list) or by name/client
- Use `load_proposal_yaml(path)` to load existing proposal

**PDF regeneration:**
- When user asks for PDF only ("cadê o PDF?"): list → find → generate (no YAML changes)

## FILE NAMING

`project_slug` must be: 3-4 words max, no accents, lowercase, hyphens only
Examples: ✅ "curso-roblox", "proposta-metaverso" ❌ "curso-de-roblox-para-jovens..."

## IMAGE HANDLING

**User-provided images:**
- When user mentions adding an image, call `wait_for_user_image(proposal_dir, position)`
- Position: "before_first_section" (default), "section_X_before", or "section_X"
- After user sends image, bot notifies you with the path
- Then: load YAML → add image → save YAML → generate PDF

**Image modifiers (YAML):**
- `image_before: file.png` → before section title
- `image: file.png` → after section content
- Place in sections, NOT in meta block

## RESPONSE STYLE

- Short and concise (2-3 lines max)
- Use past tense: "Editei a proposta" not "Vou editar"
- DO NOT include PDF path in final response (bot sends PDF automatically)
- Telegram markdown: *bold*, _italic_, `code` (no ## headers)
- Max 1-2 emojis per message
"""

    return base_instructions + bot_instructions


def normalize_slug(text: str) -> str:
    """
    Normalize text to create a safe filename slug:
    - Remove accents and special characters
    - Convert to lowercase
    - Replace spaces/underscores with hyphens
    - Remove consecutive hyphens
    """
    import unicodedata

    # Normalize unicode characters (remove accents)
    text = unicodedata.normalize('NFD', text)
    text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')

    # Convert to lowercase
    text = text.lower()

    # Replace spaces and underscores with hyphens
    text = text.replace(" ", "-").replace("_", "-")

    # Keep only alphanumeric and hyphens
    text = ''.join(char for char in text if char.isalnum() or char == '-')

    # Remove consecutive hyphens
    while '--' in text:
        text = text.replace('--', '-')

    # Remove leading/trailing hyphens
    text = text.strip('-')

    return text


@tool
def save_proposal_yaml(
    yaml_content: str,
    client_name: str = "",
    project_slug: str = "",
    date: Optional[str] = None,
    existing_file_path: Optional[str] = None
) -> str:
    """
    Save proposal YAML to submodules/tekne-proposals/docs/

    To EDIT an existing proposal, provide existing_file_path parameter.
    To CREATE a new proposal, provide client_name and project_slug.

    Args:
        yaml_content: The complete YAML content
        client_name: Client name for folder (will be slugified) - required for new proposals
        project_slug: Project name for filename (will be slugified) - required for new proposals
        date: Optional date in YYYY-MM-DD format (defaults to today)
        existing_file_path: Path to existing file to update (e.g., "docs/2025-12-sesc/proposta-metaverso.yml")

    Returns:
        Path to the saved file
    """
    # If editing existing file, use that path
    if existing_file_path:
        file_path = SUBMODULE_PATH / existing_file_path

        if not file_path.exists():
            return f"Error: File not found: {existing_file_path}"

        file_path.write_text(yaml_content, encoding="utf-8")
        relative_path = str(file_path.relative_to(SUBMODULE_PATH))
        logger.info(f"✅ Updated proposal YAML: {relative_path}")
        send_status("📝 Atualizei o arquivo da proposta!")
        return relative_path

    # Creating new proposal
    if not client_name or not project_slug:
        return "Error: client_name and project_slug are required for new proposals"

    # Parse date
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    year_month = date[:7]  # YYYY-MM

    # Normalize slugs (remove accents, special chars)
    client_slug = normalize_slug(client_name)
    project_slug = normalize_slug(project_slug)

    # Create directory path: docs/YYYY-MM-client-slug/
    dir_name = f"{year_month}-{client_slug}"
    dir_path = DOCS_PATH / dir_name
    dir_path.mkdir(parents=True, exist_ok=True)

    # Create file path: proposta-project-slug.yml
    file_name = f"proposta-{project_slug}.yml"
    file_path = dir_path / file_name

    # Save YAML
    file_path.write_text(yaml_content, encoding="utf-8")

    relative_path = str(file_path.relative_to(SUBMODULE_PATH))
    logger.info(f"✅ Created proposal YAML: {relative_path}")
    send_status("📝 Criei o arquivo da proposta!")

    return relative_path


@tool
def generate_pdf_from_yaml(yaml_file_path: str) -> str:
    """
    Generate PDF from YAML using the proposal script

    Args:
        yaml_file_path: Relative path to YAML file from submodule root

    Returns:
        Path to generated PDF file
    """
    yaml_full_path = SUBMODULE_PATH / yaml_file_path

    if not yaml_full_path.exists():
        return f"Error: YAML file not found: {yaml_file_path}"

    # Send status to user
    send_status("🔨 Gerando o PDF da proposta...")

    # Run ./proposal script
    try:
        start_time = time.time()

        result = subprocess.run(
            ["./proposal", str(yaml_file_path)],
            cwd=SUBMODULE_PATH,
            capture_output=True,
            text=True,
            timeout=30
        )

        elapsed_time = time.time() - start_time
        logger.info(f"⏱️  PDF generation took {elapsed_time:.2f} seconds")

        if result.returncode == 0:
            # Find the actual PDF file generated (it may have a different name than the YAML)
            yaml_dir = yaml_full_path.parent
            pdf_files = sorted(yaml_dir.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)

            if pdf_files:
                # Get the most recently modified PDF (the one just generated)
                pdf_path = str(pdf_files[0].relative_to(SUBMODULE_PATH))
            else:
                # Fallback to assuming same name as YAML
                pdf_path = yaml_file_path.replace('.yml', '.pdf')

            # Send status WITH PDF path so callback can detect and send it
            send_status(f"✅ PDF gerado em {elapsed_time:.1f}s! Caminho: {pdf_path}")

            logger.info(f"PDF path: {pdf_path}")
            return f"PDF gerado com sucesso: {pdf_path}"
        else:
            return f"Error generating PDF: {result.stderr}"

    except subprocess.TimeoutExpired:
        return "Error: PDF generation timed out"
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def generate_image_dalle(
    prompt: str,
    filename: str,
    yaml_file_path: str
) -> str:
    """
    Generate image using DALL-E 3 and save to proposal directory

    Args:
        prompt: Description for image generation
        filename: Name for the image file (without extension)
        yaml_file_path: Path to YAML file to save image in same directory

    Returns:
        Relative path to generated image
    """
    from openai import OpenAI
    import requests

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Generate image with DALL-E 3
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1792x1024",  # 21:9 aspect ratio (closest available)
        quality="standard",
        n=1,
    )

    image_url = response.data[0].url

    # Download image
    img_data = requests.get(image_url).content

    # Save in same directory as YAML
    yaml_full_path = SUBMODULE_PATH / yaml_file_path
    img_dir = yaml_full_path.parent
    img_path = img_dir / f"{filename}.png"

    with open(img_path, "wb") as f:
        f.write(img_data)

    return str(img_path.relative_to(SUBMODULE_PATH))


def find_proposal_images(yaml_file_path: str) -> List[str]:
    """
    Find all image files referenced in a YAML proposal

    Args:
        yaml_file_path: Path to YAML file (e.g., "docs/2025-12-sesc/proposta-x.yml")

    Returns:
        List of image file paths in the same directory
    """
    import yaml as yaml_lib

    try:
        yaml_full_path = SUBMODULE_PATH / yaml_file_path
        yaml_dir = yaml_full_path.parent

        # Read YAML and find all image references
        with open(yaml_full_path, 'r', encoding='utf-8') as f:
            data = yaml_lib.safe_load(f)

        image_files = []

        # Check sections for images
        if "sections" in data:
            for section in data["sections"]:
                if "image" in section:
                    img_path = yaml_dir / section["image"]
                    if img_path.exists():
                        image_files.append(str(img_path.relative_to(SUBMODULE_PATH)))

                if "image_before" in section:
                    img_path = yaml_dir / section["image_before"]
                    if img_path.exists():
                        image_files.append(str(img_path.relative_to(SUBMODULE_PATH)))

        # Also check for user-uploaded images in the same directory
        for img_file in yaml_dir.glob("imagem-usuario-*.jpg"):
            rel_path = str(img_file.relative_to(SUBMODULE_PATH))
            if rel_path not in image_files:
                image_files.append(rel_path)

        for img_file in yaml_dir.glob("imagem-usuario-*.png"):
            rel_path = str(img_file.relative_to(SUBMODULE_PATH))
            if rel_path not in image_files:
                image_files.append(rel_path)

        return image_files

    except Exception as e:
        logger.warning(f"Could not find images for {yaml_file_path}: {str(e)}")
        return []


@tool
def commit_and_push_submodule(
    message: str,
    files: List[str] = []
) -> str:
    """
    Commit and push changes to the tekne-proposals submodule.

    IMPORTANT: You MUST provide the 'files' parameter with a list containing the YAML file path.

    Args:
        message (str): Commit message (e.g., "Add proposal for Client - Project")
        files (List[str]): List of file paths to commit. REQUIRED - must contain at least one YAML file.
                          Example: ["docs/2025-12-sesc/proposta-metaverso.yml"]
                          Images are auto-detected from YAML and included automatically.

    Returns:
        str: Result of git operations

    Example:
        commit_and_push_submodule(
            message="Add SESC proposal",
            files=["docs/2025-12-sesc/proposta-metaverso.yml"]
        )
    """
    # Validate files parameter - must be provided
    if not files or len(files) == 0:
        error_msg = (
            "ERROR: 'files' parameter is REQUIRED!\n"
            "You must provide a list with the YAML file path.\n"
            "Example: commit_and_push_submodule(message='...', files=['docs/2025-12-sesc/proposta-x.yml'])"
        )
        logger.error(error_msg)
        send_status("❌ Erro: parâmetro 'files' não foi fornecido")
        return error_msg

    if not isinstance(files, list):
        return f"Error: 'files' must be a list of strings. Received: {type(files).__name__}"

    original_dir = os.getcwd()

    try:
        # Change to submodule directory
        os.chdir(SUBMODULE_PATH)
        logger.info(f"📁 Changed to submodule directory: {SUBMODULE_PATH}")

        # Auto-detect images from YAML files
        all_files = list(files)  # Make a copy
        for file in files:
            if file.endswith('.yml'):
                images = find_proposal_images(file)
                if images:
                    logger.info(f"🖼️  Found {len(images)} images for {file}")
                    for img in images:
                        if img not in all_files:
                            all_files.append(img)
                            logger.info(f"📎 Auto-adding image: {img}")

        send_status("📤 Enviando para o repositório...")

        # Add files
        for file in all_files:
            logger.info(f"📎 Adding file: {file}")
            result = subprocess.run(
                ["git", "add", file],
                check=True,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                logger.info(f"✓ Added: {file}")
            else:
                logger.warning(f"⚠️  Could not add {file}: {result.stderr}")

        # Commit
        logger.info(f"Committing with message: {message}")
        result = subprocess.run(
            ["git", "commit", "-m", message],
            check=True,
            capture_output=True,
            text=True
        )
        logger.info(f"Git commit output: {result.stdout}")

        # Push
        logger.info("Pushing to remote...")
        result = subprocess.run(
            ["git", "push"],
            check=True,
            capture_output=True,
            text=True
        )
        logger.info(f"Git push output: {result.stdout if result.stdout else result.stderr}")

        send_status("✅ Proposta enviada para o repositório!")

        return f"✅ Committed and pushed: {message}"

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        logger.error(f"Git error: {error_msg}")
        send_status(f"❌ Erro ao enviar: {error_msg}")
        return f"Git error: {error_msg}"
    except Exception as e:
        logger.error(f"Error in commit_and_push_submodule: {str(e)}")
        send_status(f"❌ Erro: {str(e)}")
        return f"Error: {str(e)}"
    finally:
        # Always return to original directory
        os.chdir(original_dir)
        logger.info(f"📁 Returned to original directory: {original_dir}")


@tool
def list_existing_proposals(limit: int = 10) -> str:
    """
    List existing proposals in docs/ directory, sorted by date (most recent first)

    Args:
        limit: Maximum number of proposals to return (default: 10)

    Returns:
        Formatted list of proposals with their paths
    """
    if not DOCS_PATH.exists():
        return "No proposals found. docs/ directory doesn't exist."

    proposals = []
    for project_dir in sorted(DOCS_PATH.iterdir(), reverse=True):  # Reverse sort for most recent first
        if project_dir.is_dir():
            # Find YAML files in directory
            yaml_files = list(project_dir.glob("*.yml"))
            for yaml_file in yaml_files:
                try:
                    # Read YAML to get title/client
                    with open(yaml_file, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f)
                        meta = data.get('meta', {})
                        title = meta.get('title', 'Sem título')
                        client = meta.get('client', 'Sem cliente')
                        date = meta.get('date', 'Sem data')

                        proposals.append({
                            'path': f"{project_dir.name}/{yaml_file.name}",
                            'client': client,
                            'title': title,
                            'date': date
                        })
                except Exception as e:
                    proposals.append({
                        'path': f"{project_dir.name}/{yaml_file.name}",
                        'client': 'Erro',
                        'title': 'Erro ao ler',
                        'date': 'N/A'
                    })

    if not proposals:
        return "Nenhuma proposta encontrada em docs/"

    # Limit to most recent N proposals
    proposals = proposals[:limit]

    # Format output
    formatted = []
    for i, p in enumerate(proposals, 1):
        formatted.append(f"{i}. 📄 {p['path']}\n   Cliente: {p['client']}\n   Título: {p['title']}\n   Data: {p['date']}")

    return f"Propostas mais recentes ({len(proposals)}):\n\n" + "\n\n".join(formatted)


@tool
def wait_for_user_image(proposal_dir: str, position: str = "before_first_section") -> str:
    """
    Tell the bot to wait for user to send an image via Telegram

    Args:
        proposal_dir: Directory where proposal is being created (e.g., "docs/2025-12-client")
        position: Where to place the image - options:
                 - "before_first_section" (default): image_before in first section
                 - "section_X_before": image_before in section X (e.g., "section_1_before")
                 - "section_X": image in section X (e.g., "section_0", "section_1")

    Returns:
        Confirmation message
    """
    logger.info(f"Agent requesting user image for proposal in {proposal_dir}, position: {position}")

    # Update session state to mark waiting for image
    update_session_state("current", {
        "waiting_for_image": {
            "proposal_dir": proposal_dir,
            "position": position
        }
    })

    # Don't send status here - agent will respond to user directly
    # send_status("📷 Aguardo você enviar a imagem pelo Telegram!")

    return f"Marked as waiting for user image. Position: {position}. User will send image via Telegram. Tell user you're waiting for the image."


@tool
def add_user_image_to_yaml(
    yaml_content: str,
    image_path: str,
    position: str = "before_first_section"
) -> str:
    """
    Add user-provided image to YAML content at specified position

    Args:
        yaml_content: Current YAML content
        image_path: Path to image file (relative to submodule root)
        position: Where to add the image

    Returns:
        Modified YAML content with image added
    """
    import yaml as yaml_lib

    try:
        data = yaml_lib.safe_load(yaml_content)

        if position == "before_first_section":
            # Add image_before to first section
            if "sections" in data and len(data["sections"]) > 0:
                data["sections"][0]["image_before"] = image_path
                logger.info(f"Added image_before to first section: {image_path}")

        elif position.startswith("section_") and position.endswith("_before"):
            # Add image_before to specific section (e.g., "section_1_before")
            section_idx = int(position.split("_")[1])
            if "sections" in data and len(data["sections"]) > section_idx:
                data["sections"][section_idx]["image_before"] = image_path
                logger.info(f"Added image_before to section {section_idx}: {image_path}")

        elif position.startswith("section_"):
            # Add image to specific section (e.g., "section_1")
            section_idx = int(position.split("_")[1])
            if "sections" in data and len(data["sections"]) > section_idx:
                data["sections"][section_idx]["image"] = image_path
                logger.info(f"Added image to section {section_idx}: {image_path}")

        # Convert back to YAML
        modified_yaml = yaml_lib.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
        return modified_yaml

    except Exception as e:
        logger.error(f"Error adding image to YAML: {str(e)}")
        return yaml_content  # Return original on error


@tool
def load_proposal_yaml(yaml_file_path: str) -> str:
    """
    Load existing proposal YAML for editing

    Args:
        yaml_file_path: Relative path to YAML file from submodule root

    Returns:
        YAML content as string
    """
    yaml_full_path = SUBMODULE_PATH / yaml_file_path

    if not yaml_full_path.exists():
        return f"Error: Proposal not found: {yaml_file_path}"

    try:
        content = yaml_full_path.read_text(encoding='utf-8')
        logger.info(f"Loaded proposal: {yaml_file_path}")
        return f"Conteúdo do arquivo {yaml_file_path}:\n\n```yaml\n{content}\n```"
    except Exception as e:
        return f"Error reading file: {str(e)}"


# Create the agent
proposal_agent = Agent(
    name="Tekne Proposal Generator",
    model=Claude(id="claude-sonnet-4-5"),  # Sonnet 4.5 for better accuracy
    db=InMemoryDb(),  # In-memory storage - YAML files are the source of truth
    instructions=load_claude_instructions(),
    tools=[
        save_proposal_yaml,
        generate_pdf_from_yaml,
        generate_image_dalle,
        wait_for_user_image,
        add_user_image_to_yaml,
        commit_and_push_submodule,
        list_existing_proposals,
        load_proposal_yaml,
    ],
    add_history_to_context=True,
    markdown=False,  # Disable markdown - Telegram uses different format
)


def get_agent_response(message: str, session_id: str = "default") -> str:
    """
    Get response from proposal agent

    Args:
        message: User message
        session_id: Session ID for conversation tracking

    Returns:
        Agent response text
    """
    logger.info(f"[Session {session_id}] User message: {message[:100]}...")

    # Time the API call
    start_time = time.time()
    response = proposal_agent.run(message, session_id=session_id, stream=False)
    elapsed_time = time.time() - start_time

    logger.info(f"⏱️  Claude API response time: {elapsed_time:.2f} seconds")
    logger.info(f"[Session {session_id}] Agent response length: {len(response.content)} chars")

    # Log if tools were used and check for missing commit
    tools_used = []
    if hasattr(response, 'messages'):
        for msg in response.messages:
            if hasattr(msg, 'role') and msg.role == 'assistant':
                if hasattr(msg, 'content') and msg.content is not None:
                    for block in msg.content:
                        if hasattr(block, 'type') and block.type == 'tool_use':
                            tools_used.append(block.name)
                            logger.info(f"[Session {session_id}] Tool used: {block.name}")

    # Check if agent modified proposal but didn't commit
    if 'save_proposal_yaml' in tools_used and 'commit_and_push_submodule' not in tools_used:
        logger.warning(f"⚠️  [Session {session_id}] Agent saved YAML but did NOT commit to git!")
        send_status("⚠️ Aviso: Proposta salva mas não enviada ao repositório")

    return response.content
