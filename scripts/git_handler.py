"""
Git Handler - Commits draft artifacts to the repository.
Only runs in CI (GitHub Actions) environment.
"""

import os
import subprocess
import logging

logger = logging.getLogger(__name__)


class GitHandler:
    """Handle git operations for committing drafts."""

    def __init__(self):
        self.is_ci = os.getenv("GITHUB_ACTIONS") == "true"

    def commit_draft(self, draft_path: str, log_path: str) -> bool:
        """Stage and commit the draft + log files."""
        if not self.is_ci:
            logger.info("Not in CI environment, skipping git commit")
            return False

        try:
            self._run("git config user.name 'AI Blog Bot'")
            self._run("git config user.email 'bot@users.noreply.github.com'")

            # Stage files
            self._run("git add drafts/")
            self._run("git add logs/")
            self._run("git add docs/data/ || true")

            # Check if there are changes to commit
            result = self._run("git diff --cached --quiet || echo CHANGES")
            if "CHANGES" not in result:
                logger.info("No changes to commit")
                return False

            # Commit
            self._run('git commit -m "[AUTO] Daily blog generated"')

            # Pull with rebase to avoid conflicts, then push
            self._run("git pull --rebase origin main || true")
            self._run("git push origin main")

            logger.info("Draft committed and pushed successfully")
            return True

        except Exception as e:
            logger.error(f"Git commit failed: {e}")
            return False

    def _run(self, cmd: str) -> str:
        """Run a shell command and return stdout."""
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0 and "|| true" not in cmd and "|| echo" not in cmd:
            raise RuntimeError(f"Command failed: {cmd}\nstderr: {result.stderr}")
        return result.stdout + result.stderr
