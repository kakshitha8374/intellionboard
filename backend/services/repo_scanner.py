"""
repo_scanner.py — Efficient repository scanner with:
  - Extended ignore list (bazel, cache, build artifacts, vendor dirs)
  - Configurable file/size limits to handle huge repositories
  - Priority-based scanning (README, config, source, tests)
  - Real skip-reason reporting
  - Wall-clock timeout on the directory walk (prevents indefinite hang on huge repos)
"""

import time
from pathlib import Path


# ── Directories to skip entirely ────────────────────────────────────────────

IGNORED_DIRECTORIES = {
    # Version control
    ".git",
    # IntelliOnboard internal cache — never scan this
    ".intellionboard_cache",
    # JavaScript / Node
    "node_modules",
    ".pnp",
    # Python virtualenvs
    ".venv",
    "venv",
    "env",
    ".env",
    # Python caches
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    # Build outputs
    "build",
    "dist",
    "out",
    "target",        # Rust / Maven
    "output",
    # Coverage reports
    "coverage",
    ".nyc_output",
    "htmlcov",
    # Cache directories
    ".cache",
    ".tox",
    # IDE
    ".idea",
    ".vscode",
    # Bazel (TensorFlow, etc.)
    "bazel-out",
    "bazel-bin",
    "bazel-testlogs",
    "bazel-genfiles",
    # Android / iOS
    ".gradle",
    "Pods",
    # Vendor/generated
    "vendor",
    "third_party",
    "third-party",
    "generated",
    "_generated",
    # Docs build
    "_build",
    "_site",
    "site-packages",
    # Kubernetes-specific generated dirs
    "staging",
    "_output",
    "api",           # k8s/api is mostly generated proto
}

# ── Source file extensions worth scanning ───────────────────────────────────

SOURCE_EXTENSIONS = {
    # Python
    ".py",
    # JavaScript / TypeScript
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    # Java / JVM
    ".java", ".kt", ".kts", ".scala", ".groovy",
    # C / C++
    ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hxx",
    # Systems languages
    ".go", ".rs",
    # Scripting
    ".rb", ".php", ".swift", ".cs", ".m",
    # Shell
    ".sh", ".bash", ".zsh",
    # Web
    ".html", ".css", ".scss", ".less",
    # Data / config
    ".json", ".yaml", ".yml", ".toml", ".xml", ".ini", ".cfg", ".conf",
    # Documentation
    ".md", ".rst", ".txt",
    # SQL
    ".sql",
    # Build
    ".gradle", ".cmake",
}

# ── Configurable limits ──────────────────────────────────────────────────────

MAX_FILES_TO_ANALYZE = 2000          # Maximum files to include in analysis
MAX_FILE_SIZE_BYTES = 1 * 1024 * 1024  # 1 MB per file
MAX_TOTAL_SOURCE_MB = 200            # Stop when total source exceeds 200 MB

# Wall-clock budget for the entire directory walk (seconds).
# Kubernetes has 100k+ files; we must not spend more than this scanning.
SCAN_WALK_TIMEOUT_SECONDS = 60

# ── File priority (lower number = higher priority) ───────────────────────────

def _priority(path: Path) -> int:
    """Return a scan priority for a file. Lower = more important."""
    name = path.name.lower()
    suffix = path.suffix.lower()

    # Top priority: README and key config/dependency files
    if name in {
        "readme.md", "readme.rst", "readme.txt", "readme",
        "package.json", "requirements.txt", "pyproject.toml",
        "setup.py", "setup.cfg", "cargo.toml", "go.mod",
        "pom.xml", "build.gradle", "makefile", "dockerfile",
        "docker-compose.yml", "docker-compose.yaml",
        ".env.example", "license", "license.md",
        "contributing.md", "changelog.md",
    }:
        return 0

    # Documentation
    if suffix in {".md", ".rst", ".txt"}:
        return 1

    # Config files
    if suffix in {".toml", ".yaml", ".yml", ".json", ".xml", ".ini", ".cfg", ".conf"}:
        return 2

    # Source code
    if suffix in {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".rb", ".php"}:
        return 3

    if suffix in {".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".kt", ".swift", ".scala"}:
        return 4

    # Tests
    parts = path.parts
    if any(p in {"test", "tests", "spec", "specs", "__tests__"} for p in parts):
        return 5

    return 9


def _is_likely_generated_or_minified(path: Path) -> bool:
    """Heuristic: skip obviously generated/minified files."""
    name = path.name.lower()
    stem = path.stem.lower()

    # Minified files
    if stem.endswith(".min") or ".min." in name:
        return True

    # Bundled files
    if stem.endswith(".bundle") or stem.endswith("-bundle"):
        return True

    # Common auto-generated patterns
    if name in {"package-lock.json", "yarn.lock", "pnpm-lock.yaml",
                "poetry.lock", "composer.lock", "cargo.lock",
                "pipfile.lock", "gemfile.lock"}:
        return True  # Lock files — skip to save space (huge)

    # Proto generated
    if name.endswith("_pb2.py") or name.endswith("_pb.go") or name.endswith(".pb.cc"):
        return True

    # Check for generated header in first bytes (handled in extractor)
    return False


def scan_repository(repo_path: str) -> dict:
    """
    Scan a repository and return file information with smart filtering.

    Returns real statistics — files_found, files_analyzed, files_skipped, skip_reasons.

    Bounded by SCAN_WALK_TIMEOUT_SECONDS — on very large repos (Kubernetes, Linux)
    the walk is cut short after the time limit and the files collected so far are used.
    """
    repo = Path(repo_path)

    if not repo.exists():
        return {
            "repository": repo.name,
            "file_count": 0,
            "files_analyzed": 0,
            "files_skipped": 0,
            "files": [],
            "extensions": {},
            "skip_reasons": {"repo_not_found": 1},
            "error": f"Repository path does not exist: {repo_path}",
        }

    all_files: list[Path] = []
    extensions: dict[str, int] = {}
    skip_reasons: dict[str, int] = {}

    walk_start = time.monotonic()
    walk_timed_out = False

    # ── Walk the file tree, skipping ignored directories ────────────────────
    for path in repo.rglob("*"):
        # Hard wall-clock cut-off: stop walking after timeout
        if time.monotonic() - walk_start > SCAN_WALK_TIMEOUT_SECONDS:
            walk_timed_out = True
            skip_reasons["walk_timeout"] = 1
            break

        if not path.is_file():
            continue

        # Check if any parent directory is in the ignore list
        try:
            relative = path.relative_to(repo)
        except ValueError:
            continue

        parts_lower = [p.lower() for p in relative.parts[:-1]]

        if any(part in IGNORED_DIRECTORIES or part.startswith("bazel-") for part in parts_lower):
            skip_reasons["ignored_directory"] = skip_reasons.get("ignored_directory", 0) + 1
            continue

        suffix = path.suffix.lower()

        # Extension filter
        if suffix not in SOURCE_EXTENSIONS and path.name not in {
            "Makefile", "Dockerfile", "Gemfile", "Procfile",
        }:
            skip_reasons["unsupported_extension"] = skip_reasons.get("unsupported_extension", 0) + 1
            continue

        # Generated/minified filter
        if _is_likely_generated_or_minified(path):
            skip_reasons["generated_or_lock_file"] = skip_reasons.get("generated_or_lock_file", 0) + 1
            continue

        all_files.append(path)

        if suffix:
            extensions[suffix] = extensions.get(suffix, 0) + 1

    files_found = len(all_files)

    # ── Sort by priority and apply file count + total size limits ───────────
    all_files.sort(key=_priority)

    selected_files: list[str] = []
    total_bytes = 0
    files_skipped_size = 0
    files_skipped_limit = 0

    for path in all_files:
        if len(selected_files) >= MAX_FILES_TO_ANALYZE:
            files_skipped_limit += 1
            continue

        try:
            file_size = path.stat().st_size
        except OSError:
            skip_reasons["stat_error"] = skip_reasons.get("stat_error", 0) + 1
            continue

        if file_size > MAX_FILE_SIZE_BYTES:
            skip_reasons["file_too_large"] = skip_reasons.get("file_too_large", 0) + 1
            files_skipped_size += 1
            continue

        if (total_bytes + file_size) > MAX_TOTAL_SOURCE_MB * 1024 * 1024:
            skip_reasons["total_size_limit"] = skip_reasons.get("total_size_limit", 0) + 1
            files_skipped_size += 1
            continue

        total_bytes += file_size
        try:
            selected_files.append(str(path.relative_to(repo)))
        except ValueError:
            continue

    if files_skipped_limit > 0:
        skip_reasons["file_count_limit"] = files_skipped_limit

    files_analyzed = len(selected_files)
    files_skipped = files_found - files_analyzed

    result = {
        "repository": repo.name,
        "file_count": files_found,
        "files_analyzed": files_analyzed,
        "files_skipped": files_skipped,
        "files": selected_files,
        "extensions": extensions,
        "skip_reasons": skip_reasons,
        "total_source_kb": round(total_bytes / 1024, 1),
    }

    if walk_timed_out:
        result["walk_timed_out"] = True
        result["walk_timeout_seconds"] = SCAN_WALK_TIMEOUT_SECONDS

    return result
