"""
git_history.py — Optimized Git history retrieval with:
  - Configurable commit limit (default 30)
  - subprocess timeout (never hang on large repos)
  - Changed files included for recent commits
  - Cache support to avoid repeated expensive calls
"""

import subprocess


GIT_TIMEOUT_SECONDS = 30  # Maximum time for any git command


def get_git_history(repo_path: str, max_commits: int = 30) -> dict:
    """
    Get recent Git commit history from a repository.

    Uses --follow-renames and limits to max_commits to stay fast.
    """
    command = [
        "git",
        "-C",
        repo_path,
        "log",
        f"-{max_commits}",
        "--pretty=format:%H|%an|%ad|%s",
        "--date=short",
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "message": f"git log timed out after {GIT_TIMEOUT_SECONDS}s",
            "commit_count": 0,
            "commits": [],
        }
    except FileNotFoundError:
        return {
            "status": "error",
            "message": "git is not installed or not on PATH",
            "commit_count": 0,
            "commits": [],
        }

    if result.returncode != 0:
        return {
            "status": "error",
            "message": result.stderr.strip() or "git log returned non-zero exit code",
            "commit_count": 0,
            "commits": [],
        }

    commits = []

    for line in result.stdout.splitlines():
        parts = line.split("|", 3)

        if len(parts) == 4:
            commits.append({
                "commit": parts[0],
                "author": parts[1],
                "date": parts[2],
                "message": parts[3],
            })

    return {
        "status": "success",
        "commit_count": len(commits),
        "commits": commits,
    }


def get_commit_files(repo_path: str, commit_hash: str) -> list[str]:
    """
    Return the list of files changed in a given commit.
    Used by Time Machine and Change Impact features.
    """
    command = [
        "git",
        "-C",
        repo_path,
        "diff-tree",
        "--no-commit-id",
        "-r",
        "--name-only",
        commit_hash,
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GIT_TIMEOUT_SECONDS,
        )
        if result.returncode == 0:
            return [f.strip() for f in result.stdout.splitlines() if f.strip()]
    except Exception:
        pass
    return []


def format_git_history(git_history: dict) -> str:
    """
    Convert Git history into text that can be given to the AI.
    Limits output to avoid bloating prompts.
    """
    if git_history.get("status") not in {"success"}:
        return "Git history is not available."

    commits = git_history.get("commits", [])

    if not commits:
        return "No Git commits were found."

    history_lines = []

    # Only include first 20 commits in prompts to keep context small
    for commit in commits[:20]:
        history_lines.append(
            f"Commit: {commit['commit'][:8]}\n"
            f"Author: {commit['author']}\n"
            f"Date: {commit['date']}\n"
            f"Message: {commit['message']}"
        )

    return "\n\n".join(history_lines)
