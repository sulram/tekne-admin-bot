"""
Image handling tools
"""

import os
import yaml
import logging
from typing import List
from agno.tools import tool

from config import SUBMODULE_PATH, OPENAI_API_KEY
from core.callbacks import send_status, update_session_state

logger = logging.getLogger(__name__)


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

    client = OpenAI(api_key=OPENAI_API_KEY)

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

    relative_path = str(img_path.relative_to(SUBMODULE_PATH))

    # Send status with image path so it can be sent to user
    send_status(f"✅ Imagem gerada! Caminho: {relative_path}")
    logger.info(f"✅ DALL-E image generated: {relative_path}")

    return relative_path


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
    try:
        data = yaml.safe_load(yaml_content)

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
        modified_yaml = yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
        return modified_yaml

    except Exception as e:
        logger.error(f"Error adding image to YAML: {str(e)}")
        return yaml_content  # Return original on error


def find_proposal_images(yaml_file_path: str) -> List[str]:
    """
    Find all image files referenced in a YAML proposal

    Args:
        yaml_file_path: Path to YAML file (e.g., "docs/2025-12-sesc/proposta-x.yml")

    Returns:
        List of image file paths in the same directory
    """
    try:
        yaml_full_path = SUBMODULE_PATH / yaml_file_path
        yaml_dir = yaml_full_path.parent

        # Read YAML and find all image references
        with open(yaml_full_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

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
