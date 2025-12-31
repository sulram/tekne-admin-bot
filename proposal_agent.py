"""
Tekne Proposal Generator Agent
Uses Agno with Claude to create commercial proposals following CLAUDE.md rules
"""

import os
import yaml
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional
from agno.agent import Agent
from agno.models.anthropic import Claude
from agno.db.sqlite import SqliteDb
from agno.tools import tool


# Path to submodule
SUBMODULE_PATH = Path(__file__).parent / "submodules" / "tekne-proposals"
DOCS_PATH = SUBMODULE_PATH / "docs"
CLAUDE_MD_PATH = SUBMODULE_PATH / "CLAUDE.md"


def load_claude_instructions() -> str:
    """Load CLAUDE.md as agent instructions"""
    if CLAUDE_MD_PATH.exists():
        return CLAUDE_MD_PATH.read_text()
    return "Generate proposals in YAML format for Tekne Studio."


@tool
def save_proposal_yaml(
    yaml_content: str,
    client_name: str,
    project_slug: str,
    date: Optional[str] = None
) -> str:
    """
    Save proposal YAML to submodules/tekne-proposals/docs/

    Args:
        yaml_content: The complete YAML content
        client_name: Client name for folder (will be slugified)
        project_slug: Project name for filename (will be slugified)
        date: Optional date in YYYY-MM-DD format (defaults to today)

    Returns:
        Path to the created file
    """
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

    return str(file_path.relative_to(SUBMODULE_PATH))


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

    # Run ./proposal script
    try:
        result = subprocess.run(
            ["./proposal", str(yaml_file_path)],
            cwd=SUBMODULE_PATH,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
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
def commit_and_push_submodule(message: str, files: list[str]) -> str:
    """
    Commit and push changes to the tekne-proposals submodule

    Args:
        message: Commit message
        files: List of file paths to add (relative to submodule root)

    Returns:
        Result of git operations
    """
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


# Create the agent
proposal_agent = Agent(
    name="Tekne Proposal Generator",
    model=Claude(id="claude-sonnet-4-5"),
    db=SqliteDb(db_file="proposals.db"),
    instructions=load_claude_instructions(),
    tools=[
        save_proposal_yaml,
        generate_pdf_from_yaml,
        generate_image_dalle,
        commit_and_push_submodule,
    ],
    add_history_to_context=True,
    markdown=True,
    show_tool_calls=True,
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
    response = proposal_agent.run(message, session_id=session_id, stream=False)
    return response.content
