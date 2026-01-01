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

        # Add all changes
        subprocess.run(["git", "add", "."], check=True, capture_output=True, text=True)
        logger.info("✓ Added all changes (git add .)")

        # Commit
        logger.info(f"Committing with message: {message}")
        result = subprocess.run(
            ["git", "commit", "-m", message],
            check=True,
            capture_output=True,
            text=True
        )
        logger.info(f"Git commit output: {result.stdout}")

        # Sync with remote using stash + reset + apply strategy
        logger.info("Syncing with remote (stash + reset + apply)...")

        # Step 1: Stash local commit (includes new commit we just made)
        logger.info("Stashing local changes...")
        subprocess.run(["git", "reset", "HEAD~1"], capture_output=True)  # Undo commit but keep changes
        subprocess.run(["git", "stash", "push", "-u", "-m", f"Auto-stash: {message}"], capture_output=True)

        # Step 2: Fetch and reset to origin/main
        logger.info("Fetching and resetting to origin/main...")
        subprocess.run(["git", "fetch", "origin", "main"], check=True, capture_output=True)
        subprocess.run(["git", "reset", "--hard", "origin/main"], check=True, capture_output=True)

        # Step 3: Apply stashed changes (accept all incoming in case of conflict)
        logger.info("Applying stashed changes...")
        stash_result = subprocess.run(
            ["git", "stash", "pop"],
            capture_output=True,
            text=True
        )

        # If stash pop had conflicts, accept all "ours" (incoming = our changes)
        if stash_result.returncode != 0:
            logger.warning("Stash pop had conflicts, accepting our changes...")
            # Accept all our changes
            subprocess.run(["git", "checkout", "--ours", "."], capture_output=True)
            subprocess.run(["git", "add", "."], capture_output=True)
            # Clear stash
            subprocess.run(["git", "stash", "drop"], capture_output=True)

        # Step 4: Check if there are changes to commit
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True
        )

        if not status_result.stdout.strip():
            # No changes to commit (already up to date)
            logger.info("No changes to commit - already synchronized with remote")
            send_status("✅ Proposta já estava sincronizada no repositório!")
            return f"✅ No changes needed - already synchronized"

        # Step 5: Commit the changes
        logger.info(f"Committing synced changes: {message}")
        result = subprocess.run(
            ["git", "commit", "-m", message],
            check=True,
            capture_output=True,
            text=True
        )
        logger.info(f"Git commit output: {result.stdout}")

        # Step 6: Push to remote
        logger.info("Pushing to remote...")
        result = subprocess.run(
            ["git", "push", "--set-upstream", "origin", "main"],
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
