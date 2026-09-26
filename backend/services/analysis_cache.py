"""
analysis_cache.py — Repository analysis result cache.

Caches expensive analysis results keyed on (repo_name, git_head_commit).
When the HEAD commit changes (new push), the cache is automatically invalidated.
Uses JSON files stored in .intellionboard_cache/ inside each repo.

Also provides a simple in-memory AI response cache for identical requests.

Key rules:
  - A cached result is only trusted if it has file_count > 0 or commit_count > 0
  - Results with head_commit == "unknown" are never persisted
  - Two "unknown" heads do NOT match — forces re-analysis on broken clones
"""

import json
import hashlib
import subprocess
from pathlib import Path
from typing import Any


# ── Repository analysis cache ─────────────────────────────────────────────────

CACHE_DIR_NAME = ".intellionboard_cache"


def _get_cache_dir(repo_path: str) -> Path:
    """Return (and create if needed) the cache directory for a repo."""
    cache_dir = Path(repo_path) / CACHE_DIR_NAME
    cache_dir.mkdir(exist_ok=True)
    return cache_dir


def _get_head_commit(repo_path: str) -> str:
    """Return the current HEAD commit hash or 'unknown' if unavailable."""
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            head = result.stdout.strip()
            if head and len(head) >= 10:
                return head[:12]
    except Exception:
        pass
    return "unknown"


def _cache_key(cache_type: str, repo_path: str, extra: str = "") -> str:
    """Build a cache key from repo path + HEAD commit + optional extra."""
    head = _get_head_commit(repo_path)
    raw = f"{cache_type}:{repo_path}:{head}:{extra}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _is_useful_result(value: Any) -> bool:
    """
    Return True only if the cached analysis result contains real data.

    A result with 0 files, 0 commits is NOT considered useful —
    it indicates a broken/incomplete clone and must not be cached or served.
    """
    if not isinstance(value, dict):
        return False
    scan = value.get("scan", {})
    git = value.get("git_history", {})
    code = value.get("code_structure", {})

    files_analyzed = scan.get("files_analyzed", 0) or scan.get("file_count", 0)
    commits = git.get("commit_count", 0)
    classes = code.get("class_count", 0)
    functions = code.get("function_count", 0)

    # Require at least some files OR some commits — otherwise the clone was broken
    return (files_analyzed > 0) or (commits > 0) or (classes > 0) or (functions > 0)


def load_cache(cache_type: str, repo_path: str, extra: str = "") -> Any | None:
    """
    Load a cached result. Returns None if:
      - Cache file does not exist
      - HEAD commit has changed (repo updated)
      - HEAD commit is 'unknown' — broken clone, never trust
      - Cached result has 0 files and 0 commits (empty analysis)
    """
    # Never trust a repo where HEAD is unknown (incomplete clone)
    current_head = _get_head_commit(repo_path)
    if current_head == "unknown":
        return None

    cache_dir = _get_cache_dir(repo_path)
    key = _cache_key(cache_type, repo_path, extra)
    cache_file = cache_dir / f"{cache_type}_{key}.json"

    if not cache_file.exists():
        return None

    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        stored_head = data.get("_head_commit")

        # Both heads must be real commit hashes and must match
        if not stored_head or stored_head == "unknown":
            return None
        if stored_head != current_head:
            return None  # Cache invalidated — repo has changed

        value = data.get("_value")

        # Never serve an empty result
        if not _is_useful_result(value):
            return None

        return value

    except Exception:
        return None


def save_cache(cache_type: str, repo_path: str, value: Any, extra: str = "") -> None:
    """
    Save a result to the cache.
    Only saves when HEAD is a real commit and the result has actual data.
    """
    try:
        # Never cache results from broken clones or empty analyses
        head = _get_head_commit(repo_path)
        if head == "unknown":
            return

        if not _is_useful_result(value):
            return

        cache_dir = _get_cache_dir(repo_path)
        key = _cache_key(cache_type, repo_path, extra)
        cache_file = cache_dir / f"{cache_type}_{key}.json"

        payload = {
            "_head_commit": head,
            "_value": value,
        }

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, default=str)

    except Exception:
        pass  # Cache write failures are non-fatal


def clear_repo_cache(repo_path: str) -> int:
    """
    Remove all cached analysis files for a repository.
    Returns the number of files removed.
    """
    removed = 0
    try:
        cache_dir = Path(repo_path) / CACHE_DIR_NAME
        if cache_dir.exists():
            for f in cache_dir.glob("*.json"):
                try:
                    f.unlink()
                    removed += 1
                except Exception:
                    pass
    except Exception:
        pass
    return removed


# ── In-memory AI response cache ───────────────────────────────────────────────

_AI_CACHE: dict[str, str] = {}
_AI_CACHE_MAX = 200


def _ai_cache_key(feature: str, repo_name: str, prompt_hash: str) -> str:
    raw = f"{feature}:{repo_name}:{prompt_hash}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def get_ai_cache(feature: str, repo_name: str, prompt: str) -> str | None:
    """Return a cached AI response for an identical prompt, or None."""
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:20]
    key = _ai_cache_key(feature, repo_name, prompt_hash)
    return _AI_CACHE.get(key)


def set_ai_cache(feature: str, repo_name: str, prompt: str, response: str) -> None:
    """Store an AI response in memory cache."""
    if len(_AI_CACHE) >= _AI_CACHE_MAX:
        keys = list(_AI_CACHE.keys())
        for k in keys[: len(keys) // 2]:
            _AI_CACHE.pop(k, None)

    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:20]
    key = _ai_cache_key(feature, repo_name, prompt_hash)
    _AI_CACHE[key] = response
