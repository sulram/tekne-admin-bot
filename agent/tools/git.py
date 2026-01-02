"""
Git operations tools
"""

import os
import logging
import subprocess
from agno.tools import tool

from config import SUBMODULE_PATH
from core.callbacks import send_status

logger = logging.getLogger(__name__)


@tool
def commit_and_push_submodule(message: str) -> str:
    """
    Commit and push ALL changes in the tekne-proposals submodule.

    This will add all modified files (YAMLs and images) to git, commit, and push.

    Args:
        message (str): Commit message (e.g., "Update proposal for Client X")

    Returns:
        str: Result of git operations

    Example:
        commit_and_push_submodule("Update SESC proposal")
    """
    original_dir = os.getcwd()

    try:
        # Change to submodule directory
        os.chdir(SUBMODULE_PATH)
        logger.info(f"📁 Changed to submodule directory: {SUBMODULE_PATH}")

        # Check if this is a valid git repository first
        git_check = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True
        )

        if git_check.returncode != 0:
            logger.warning("⚠️  Not a git repository - skipping git commit/push")
            logger.info("ℹ️  This is expected in Docker without git initialization")
            return "⚠️  Git não configurado neste ambiente. O PDF foi gerado com sucesso, mas não foi enviado ao repositório."

        send_status("📤 Enviando para o repositório...")

        # Ensure we're on main branch (fix detached HEAD state)
        try:
            branch_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                check=True,
                capture_output=True,
                text=True
            )
            current_branch = branch_result.stdout.strip()
            logger.info(f"Current branch: {current_branch}")

            if current_branch == "HEAD":  # Detached HEAD state
                logger.info("Detached HEAD detected, checking out main branch...")
                subprocess.run(["git", "checkout", "main"], check=True, capture_output=True, text=True)
                logger.info("✓ Checked out main branch")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Could not check/fix branch state: {e.stderr}")

        # Strategy: temp branch + force reset + merge
        # This prevents "unrelated histories" issues when template changes happen remotely

        # 1. Fetch latest from remote
        logger.info("Fetching latest from remote...")
        subprocess.run(["git", "fetch", "origin", "main"], check=True, capture_output=True, text=True)
        logger.info("✓ Fetched origin/main")

        # 2. Create temporary branch with agent's changes
        temp_branch = "temp-agent-changes"
        logger.info(f"Creating temporary branch: {temp_branch}")
        subprocess.run(["git", "checkout", "-b", temp_branch], check=True, capture_output=True, text=True)
        logger.info(f"✓ Created branch {temp_branch}")

        # 3. Add and commit changes in temp branch
        subprocess.run(["git", "add", "."], check=True, capture_output=True, text=True)
        logger.info("✓ Added all changes (git add .)")

        logger.info(f"Committing with message: {message}")
        result = subprocess.run(
            ["git", "commit", "-m", message],
            check=True,
            capture_output=True,
            text=True
        )
        logger.info(f"Git commit output: {result.stdout}")

        # 4. Checkout main and force reset to remote
        logger.info("Checking out main and syncing with remote...")
        subprocess.run(["git", "checkout", "main"], check=True, capture_output=True, text=True)
        subprocess.run(["git", "reset", "--hard", "origin/main"], check=True, capture_output=True, text=True)
        logger.info("✓ Reset main to origin/main (hard)")

        # 5. Merge temp branch (prefer agent's changes in conflicts)
        logger.info(f"Merging {temp_branch} into main...")
        result = subprocess.run(
            ["git", "merge", temp_branch, "--no-ff", "-X", "ours", "-m", f"Merge agent changes: {message}"],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            logger.info(f"✓ Merge successful: {result.stdout if result.stdout else result.stderr}")
        else:
            logger.warning(f"Merge had issues: {result.stderr}")
            # Continue to push anyway - might be just warnings

        # 6. Clean up temp branch
        logger.info(f"Deleting temporary branch {temp_branch}...")
        subprocess.run(["git", "branch", "-D", temp_branch], check=True, capture_output=True, text=True)
        logger.info(f"✓ Deleted {temp_branch}")

        # 7. Push to remote
        logger.info("Pushing to remote...")
        result = subprocess.run(
            ["git", "push", "origin", "main"],
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
        os.chdir(original_dir)
        logger.info(f"📁 Returned to original directory: {original_dir}")
