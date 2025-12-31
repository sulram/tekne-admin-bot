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

def set_status_callback(callback: Callable[[str], None]) -> None:
    """Set callback function to send status updates to user"""
    global _status_callback
    _status_callback = callback

def send_status(message: str) -> None:
    """Send status message to user if callback is set"""
    if _status_callback:
        _status_callback(message)


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

## WORKFLOW INSTRUCTIONS (Telegram Bot)

**IMPORTANT: You MUST follow this workflow after saving/generating proposals:**

1. After calling `save_proposal_yaml` or editing a YAML file:
   - The file is saved to the git repository

2. After calling `generate_pdf_from_yaml`:
   - The PDF is generated in the same directory

3. **ALWAYS commit and push changes** using `commit_and_push_submodule`:
   - Include YAML files and images (DO NOT include PDF files)
   - Use descriptive commit message (e.g., "Add proposal for [Client] - [Project]")
   - Example: `commit_and_push_submodule("Add SESC proposal - Youth and Climate Change", ["docs/2025-12-sesc/proposta-metaverso.yml"])`

**DO NOT skip the commit step!** All proposals must be versioned in git.
**DO NOT commit PDF files** - only YAML and images.
"""

    return base_instructions + bot_instructions


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

    # Slugify names
    client_slug = client_name.lower().replace(" ", "-").replace("_", "-")
    project_slug = project_slug.lower().replace(" ", "-").replace("_", "-")

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
            send_status(f"✅ PDF gerado em {elapsed_time:.1f}s!")

            # Extract PDF path from output
            # The script outputs: "✓ Generated: path/to/file.pdf"
            for line in result.stdout.split("\n"):
                if "Generated:" in line or "✓" in line:
                    pdf_path = line.split(":")[-1].strip()
                    return pdf_path

            return "PDF generated successfully"
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


@tool
def commit_and_push_submodule(message: str, files: List[str]) -> str:
    """
    Commit and push changes to the tekne-proposals submodule

    Args:
        message: Commit message (e.g., "Add proposal for Client - Project")
        files: List of file paths to commit (e.g., ["docs/2025-12-client/proposta-project.yml"])
               REQUIRED - must be a list of strings, cannot be empty or None

    Returns:
        Result of git operations

    Example:
        commit_and_push_submodule(
            message="Add SESC proposal",
            files=["docs/2025-12-sesc/proposta-metaverso.yml"]
        )
    """
    # Validate files parameter
    if not files or not isinstance(files, list):
        return f"Error: 'files' parameter must be a non-empty list of file paths. Received: {files}"

    try:
        # Change to submodule directory
        os.chdir(SUBMODULE_PATH)

        # Add files
        for file in files:
            subprocess.run(["git", "add", file], check=True)

        # Commit
        subprocess.run(
            ["git", "commit", "-m", message],
            check=True,
            capture_output=True
        )

        # Push
        subprocess.run(
            ["git", "push"],
            check=True,
            capture_output=True
        )

        # Return to parent directory
        os.chdir(SUBMODULE_PATH.parent)

        return f"✅ Committed and pushed: {message}"

    except subprocess.CalledProcessError as e:
        return f"Git error: {e.stderr.decode() if e.stderr else str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def list_existing_proposals() -> str:
    """
    List all existing proposals in docs/ directory

    Returns:
        Formatted list of proposals with their paths
    """
    if not DOCS_PATH.exists():
        return "No proposals found. docs/ directory doesn't exist."

    proposals = []
    for project_dir in sorted(DOCS_PATH.iterdir()):
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

                        proposals.append(f"📄 {project_dir.name}/{yaml_file.name}\n   Cliente: {client}\n   Título: {title}\n   Data: {date}")
                except Exception as e:
                    proposals.append(f"❌ {project_dir.name}/{yaml_file.name} (erro ao ler)")

    if not proposals:
        return "Nenhuma proposta encontrada em docs/"

    return "Propostas existentes:\n\n" + "\n\n".join(proposals)


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
    model=Claude(id="claude-haiku-4-5"),  # Using Haiku for cost efficiency
    db=InMemoryDb(),  # In-memory storage - YAML files are the source of truth
    instructions=load_claude_instructions(),
    tools=[
        save_proposal_yaml,
        generate_pdf_from_yaml,
        generate_image_dalle,
        commit_and_push_submodule,
        list_existing_proposals,
        load_proposal_yaml,
    ],
    add_history_to_context=True,
    markdown=True,
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

    # Log if tools were used
    if hasattr(response, 'messages'):
        for msg in response.messages:
            if hasattr(msg, 'role') and msg.role == 'assistant':
                if hasattr(msg, 'content') and msg.content is not None:
                    for block in msg.content:
                        if hasattr(block, 'type') and block.type == 'tool_use':
                            logger.info(f"[Session {session_id}] Tool used: {block.name}")

    return response.content
