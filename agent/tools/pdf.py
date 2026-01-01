"""
PDF generation tools
"""

import logging
import time
import subprocess
from agno.tools import tool

from config import SUBMODULE_PATH
from core.callbacks import send_status

logger = logging.getLogger(__name__)


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
