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


def _generate_pdf_impl(yaml_file_path: str) -> str:
    """
    Internal implementation: Generate PDF from YAML using the proposal script
    This is the actual function that does the work, callable from anywhere.

    Args:
        yaml_file_path: Relative path to YAML file from submodule root

    Returns:
        Path to generated PDF file
    """
    yaml_full_path = SUBMODULE_PATH / yaml_file_path

    if not yaml_full_path.exists():
        return f"Error: YAML file not found: {yaml_file_path}"

    # Send status to user (only if callback is available)
    try:
        send_status("🔨 Gerando o PDF da proposta...")
    except:
        pass  # Ignore if no callback context

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
        logger.info(f"📋 Subprocess returncode: {result.returncode}")
        logger.info(f"📋 Subprocess stdout: {result.stdout[:200] if result.stdout else 'None'}")
        logger.info(f"📋 Subprocess stderr: {result.stderr[:200] if result.stderr else 'None'}")

        if result.returncode == 0:
            # Find the actual PDF file generated (it may have a different name than the YAML)
            yaml_dir = yaml_full_path.parent
            pdf_files = sorted(yaml_dir.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)

            if pdf_files:
                # Get the most recently modified PDF (the one just generated)
                pdf_path = str(pdf_files[0].relative_to(SUBMODULE_PATH))
                logger.info(f"✅ Found PDF file: {pdf_path}")
            else:
                # Fallback to assuming same name as YAML
                pdf_path = yaml_file_path.replace('.yml', '.pdf')
                logger.warning(f"⚠️  No PDF files found in {yaml_dir}, using fallback: {pdf_path}")

            # Send status WITH PDF path so callback can detect and send it
            logger.info(f"📤 Sending status with PDF path: {pdf_path}")
            send_status(f"✅ PDF gerado em {elapsed_time:.1f}s! Caminho: {pdf_path}")

            logger.info(f"✅ PDF generation complete: {pdf_path}")
            return f"PDF gerado com sucesso: {pdf_path}"
        else:
            error_msg = result.stderr if result.stderr else result.stdout
            logger.error(f"❌ PDF generation failed (returncode {result.returncode}): {error_msg}")

            # Check for typst not installed
            if "typst not installed" in error_msg:
                return "❌ ERRO CRÍTICO: Typst não está instalado no servidor. Notifique o administrador."

            return f"❌ Erro ao gerar PDF: {error_msg}"

    except subprocess.TimeoutExpired:
        logger.error("PDF generation timed out")
        return "Error: PDF generation timed out"
    except Exception as e:
        logger.error(f"Exception in _generate_pdf_impl: {e}", exc_info=True)
        return f"Error: {str(e)}"


# Simple function for direct use (bot commands, etc)
generate_pdf_from_yaml = _generate_pdf_impl


# Agent-compatible wrapper with @tool decorator
@tool
def generate_pdf_from_yaml_tool(yaml_file_path: str) -> str:
    """
    Generate PDF from YAML using the proposal script (Agent tool wrapper)

    Args:
        yaml_file_path: Relative path to YAML file from submodule root

    Returns:
        Path to generated PDF file
    """
    return _generate_pdf_impl(yaml_file_path)
