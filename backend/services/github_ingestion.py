"""
github_ingestion.py — Optimized repository cloning with:
  - Shallow clone (depth=50) for fast initial analysis
  - Clone integrity validation — detects broken/incomplete clones
  - subprocess timeout to prevent hanging on huge repos
  - Windows long-path detection (Kubernetes has paths > 260 chars)
  - Proper error handling and useful error messages
"""

import subprocess
import shutil
import platform
from pathlib import Path


# Maximum seconds allowed for a git clone operation.
# Kubernetes is ~2 GB shallow — 600 s is the outer wall on slow networks.
CLONE_TIMEOUT_SECONDS = 600  # 10 minutes

# Warn threshold: repos this many bytes or more get an extra log note
LARGE_REPO_BYTES = 500 * 1024 * 1024   # 500 MB


def _is_valid_clone(repo_path: Path) -> bool:
    """
    Check whether an existing directory is a valid, usable Git clone.

    A clone is considered valid only when:
      - The directory contains a .git subdirectory (or file for submodules)
      - git rev-parse HEAD succeeds (i.e. at least one commit is present)
      - The working tree has actual files beyond just .git

    Returns False for:
      - Empty directories
      - Partial / interrupted clones (no HEAD, no objects)
      - Directories that happen to share the repo name but aren't git repos
    """
    if not repo_path.exists():
        return False

    git_dir = repo_path / ".git"
    if not git_dir.exists():
        return False

    # git rev-parse HEAD must succeed — fails on incomplete clones
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return False
        head_hash = result.stdout.strip()
        if not head_hash or len(head_hash) < 10:
            return False
    except Exception:
        return False

    # Must have at least some non-.git files
    try:
        non_git_items = [
            p for p in repo_path.iterdir()
            if p.name not in {".git", ".intellionboard_cache"}
        ]
        if len(non_git_items) == 0:
            return False
    except Exception:
        return False

    return True


def _remove_broken_clone(repo_path: Path) -> None:
    """Remove a directory that contains an incomplete or corrupt clone."""
    try:
        shutil.rmtree(repo_path)
    except Exception:
        pass


def _check_windows_long_paths() -> bool:
    """
    Return True if Windows long-path support is likely enabled.
    On Windows, paths > 260 chars fail by default unless the registry
    key LongPathsEnabled=1 is set AND git is configured with core.longpaths.
    """
    if platform.system() != "Windows":
        return True  # Non-Windows — no issue

    try:
        result = subprocess.run(
            ["git", "config", "--system", "core.longpaths"],
            capture_output=True, text=True, timeout=5,
        )
        if result.stdout.strip().lower() == "true":
            return True
    except Exception:
        pass
    return False


def clone_repository(repo_url: str, repo_name: str) -> dict:
    """
    Clone a GitHub repository with a shallow depth for efficient initial analysis.

    If the target directory already exists but is NOT a valid git clone
    (e.g. an interrupted previous clone), it is automatically removed and
    re-cloned so the caller always gets a usable repository.

    Uses --depth 50 to avoid downloading the entire history.
    Returns detailed status information.
    """
    repos_dir = Path("repos")
    repos_dir.mkdir(exist_ok=True)

    repo_path = repos_dir / repo_name

    # ── Already exists: validate before trusting it ──────────────────────────
    if repo_path.exists():
        if _is_valid_clone(repo_path):
            return {
                "status": "already_exists",
                "path": str(repo_path),
                "message": f"Repository '{repo_name}' already exists and is valid.",
            }
        else:
            # Broken / incomplete clone — remove and re-clone
            _remove_broken_clone(repo_path)
            # Fall through to fresh clone below

    # ── Windows long-path warning ────────────────────────────────────────────
    windows_long_paths_ok = _check_windows_long_paths()
    long_path_warning = None
    if not windows_long_paths_ok:
        long_path_warning = (
            "Windows long-path support is NOT enabled. "
            "Repositories with deep directory structures (e.g. Kubernetes) may "
            "fail to clone or check out some files. "
            "To fix: run `git config --system core.longpaths true` as Administrator "
            "and enable LongPathsEnabled in the Windows registry."
        )

    # ── Fresh clone ──────────────────────────────────────────────────────────
    command = [
        "git",
        "clone",
        "--depth", "50",       # Shallow clone — only recent 50 commits
        "--single-branch",     # Only default branch
        "--no-tags",           # Skip tags to reduce download size
        repo_url,
        str(repo_path),
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=CLONE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        _remove_broken_clone(repo_path)
        raise RuntimeError(
            f"Repository clone timed out after {CLONE_TIMEOUT_SECONDS}s. "
            "The repository may be too large or the network is slow. "
            "Try again — the shallow clone will be retried from scratch."
        )
    except FileNotFoundError:
        raise RuntimeError(
            "git is not installed or not available on PATH. "
            "Please install git to use IntelliOnboard."
        )

    if result.returncode != 0:
        _remove_broken_clone(repo_path)
        stderr = result.stderr.strip()

        # Windows long-path specific error patterns
        if platform.system() == "Windows" and any(k in stderr for k in (
            "Filename too long", "invalid path", "unable to create file",
            "Could not create directory", "error: unable to checkout"
        )):
            raise RuntimeError(
                f"Clone failed due to Windows path-length limitations: {stderr}\n"
                "Fix: run `git config --system core.longpaths true` as Administrator, "
                "then re-analyze. Alternatively, enable Developer Mode in Windows Settings."
            )

        if "Repository not found" in stderr or "does not exist" in stderr:
            raise RuntimeError(
                f"Repository not found: '{repo_url}'. "
                "Check the URL and ensure the repository is public."
            )
        if "Authentication failed" in stderr:
            raise RuntimeError(
                "Authentication failed. IntelliOnboard only supports public repositories."
            )
        raise RuntimeError(
            f"Git clone failed for '{repo_url}': {stderr or 'unknown error'}"
        )

    clone_info = {
        "status": "cloned",
        "path": str(repo_path),
        "message": f"Repository '{repo_name}' cloned successfully (shallow depth=50).",
    }
    if long_path_warning:
        clone_info["long_path_warning"] = long_path_warning

    return clone_info
