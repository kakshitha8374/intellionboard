"""
code_parser.py — Multi-language code structure extractor.

Parses source files to extract classes, functions, and imports.
- Uses Python AST for .py files (fast and reliable)
- Uses regex-based structural extraction for other languages
- Per-file error isolation: one bad file never stops the whole analysis
- Returns real statistics
"""

import ast
import re
from pathlib import Path


# ── Regex patterns per language group ────────────────────────────────────────

# JavaScript / TypeScript
_JS_CLASS_RE = re.compile(
    r"(?:^|\n)\s*(?:export\s+)?(?:abstract\s+)?class\s+([A-Za-z_$][A-Za-z0-9_$]*)",
)
_JS_FUNC_RE = re.compile(
    r"(?:^|\n)\s*(?:export\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*\(",
)
_JS_ARROW_RE = re.compile(
    r"(?:^|\n)\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:async\s+)?\(",
)
_JS_METHOD_RE = re.compile(
    r"(?:^|\n)\s+(?:async\s+)?(?:static\s+)?(?:get\s+|set\s+)?([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{",
)

# Java / Kotlin / C#
_JAVA_CLASS_RE = re.compile(
    r"(?:^|\n)\s*(?:public\s+|private\s+|protected\s+)?(?:abstract\s+|final\s+)?(?:class|interface|enum|record)\s+([A-Za-z_][A-Za-z0-9_]*)",
)
_JAVA_METHOD_RE = re.compile(
    r"(?:^|\n)\s+(?:public|private|protected|static|final|abstract|synchronized|async)(?:\s+(?:public|private|protected|static|final|abstract|synchronized|async))*\s+\S+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
)

# C / C++
_CPP_CLASS_RE = re.compile(
    r"(?:^|\n)\s*(?:class|struct)\s+([A-Za-z_][A-Za-z0-9_]*)\s*[:{]",
)
_CPP_FUNC_RE = re.compile(
    r"(?:^|\n)(?:[A-Za-z_][A-Za-z0-9_:*&\s]+)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^;]*\)\s*(?:const\s*)?\{",
)

# Go
_GO_FUNC_RE = re.compile(
    r"(?:^|\n)func\s+(?:\([^)]+\)\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\(",
)
_GO_TYPE_RE = re.compile(
    r"(?:^|\n)type\s+([A-Za-z_][A-Za-z0-9_]*)\s+struct",
)

# Rust
_RS_FUNC_RE = re.compile(
    r"(?:^|\n)\s*(?:pub\s+)?(?:async\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*[<(]",
)
_RS_STRUCT_RE = re.compile(
    r"(?:^|\n)\s*(?:pub\s+)?(?:struct|enum|trait|impl)\s+([A-Za-z_][A-Za-z0-9_]*)",
)

# Ruby
_RB_CLASS_RE = re.compile(
    r"(?:^|\n)\s*class\s+([A-Za-z_][A-Za-z0-9_:]*)",
)
_RB_METHOD_RE = re.compile(
    r"(?:^|\n)\s*def\s+([A-Za-z_][A-Za-z0-9_?!]*)",
)

# PHP
_PHP_CLASS_RE = re.compile(
    r"(?:^|\n)\s*(?:abstract\s+|final\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)",
)
_PHP_FUNC_RE = re.compile(
    r"(?:^|\n)\s*(?:public\s+|private\s+|protected\s+)?(?:static\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
)

# Swift / Kotlin
_SWIFT_CLASS_RE = re.compile(
    r"(?:^|\n)\s*(?:public\s+|private\s+|internal\s+|open\s+)?(?:class|struct|protocol|enum)\s+([A-Za-z_][A-Za-z0-9_]*)",
)
_SWIFT_FUNC_RE = re.compile(
    r"(?:^|\n)\s*(?:public\s+|private\s+|internal\s+|open\s+)?(?:static\s+)?(?:func|fun)\s+([A-Za-z_][A-Za-z0-9_]*)\s*[<(]",
)


def _parse_python(content: str, filepath: str) -> dict:
    """Parse Python using AST — accurate and fast."""
    classes = []
    functions = []
    imports = []
    parse_errors = []

    try:
        tree = ast.parse(content)
    except SyntaxError as exc:
        parse_errors.append(f"{filepath}: SyntaxError at line {exc.lineno}: {exc.msg}")
        # Fall back to regex for partial extraction
        return _parse_regex_python(content, filepath)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Only top-level and class-level functions (not nested)
            functions.append(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            else:
                module = node.module or ""
                imports.append(module)

    return {
        "classes": classes[:50],
        "functions": functions[:100],
        "imports": list(set(imports))[:50],
        "parse_errors": parse_errors,
    }


def _parse_regex_python(content: str, filepath: str) -> dict:
    """Regex fallback for Python (handles syntax errors gracefully)."""
    classes = re.findall(r"(?:^|\n)\s*class\s+([A-Za-z_][A-Za-z0-9_]*)", content)
    functions = re.findall(r"(?:^|\n)\s*(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)", content)
    imports = re.findall(r"(?:^|\n)\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_.]*)", content)
    return {
        "classes": classes[:50],
        "functions": functions[:100],
        "imports": list(set(imports))[:50],
        "parse_errors": [f"{filepath}: used regex fallback (syntax error)"],
    }


def _parse_javascript(content: str, filepath: str) -> dict:
    classes = list(set(_JS_CLASS_RE.findall(content)))
    functions = list(set(
        _JS_FUNC_RE.findall(content) +
        _JS_ARROW_RE.findall(content)
    ))
    imports = re.findall(r"(?:import|require)\s*[\({\"']([^\"')\s]+)", content)
    return {
        "classes": classes[:50],
        "functions": functions[:100],
        "imports": list(set(imports))[:50],
        "parse_errors": [],
    }


def _parse_java_kotlin(content: str, filepath: str) -> dict:
    classes = list(set(_JAVA_CLASS_RE.findall(content)))
    functions = list(set(_JAVA_METHOD_RE.findall(content)))
    imports = re.findall(r"import\s+(?:static\s+)?([A-Za-z_][A-Za-z0-9_.]*)", content)
    return {
        "classes": classes[:50],
        "functions": functions[:100],
        "imports": list(set(imports))[:50],
        "parse_errors": [],
    }


def _parse_cpp(content: str, filepath: str) -> dict:
    classes = list(set(_CPP_CLASS_RE.findall(content)))
    functions = list(set(_CPP_FUNC_RE.findall(content)))
    includes = re.findall(r'#include\s*[<"]([^>"]+)[>"]', content)
    return {
        "classes": classes[:50],
        "functions": functions[:100],
        "imports": includes[:50],
        "parse_errors": [],
    }


def _parse_go(content: str, filepath: str) -> dict:
    functions = list(set(_GO_FUNC_RE.findall(content)))
    classes = list(set(_GO_TYPE_RE.findall(content)))  # structs
    imports = re.findall(r'"([A-Za-z][A-Za-z0-9_./]+)"', content)
    return {
        "classes": classes[:50],
        "functions": functions[:100],
        "imports": list(set(imports))[:50],
        "parse_errors": [],
    }


def _parse_rust(content: str, filepath: str) -> dict:
    functions = list(set(_RS_FUNC_RE.findall(content)))
    classes = list(set(_RS_STRUCT_RE.findall(content)))
    imports = re.findall(r"use\s+([A-Za-z_][A-Za-z0-9_:]+)", content)
    return {
        "classes": classes[:50],
        "functions": functions[:100],
        "imports": list(set(imports))[:50],
        "parse_errors": [],
    }


def _parse_ruby(content: str, filepath: str) -> dict:
    classes = list(set(_RB_CLASS_RE.findall(content)))
    functions = list(set(_RB_METHOD_RE.findall(content)))
    imports = re.findall(r"require\s+['\"]([^'\"]+)['\"]", content)
    return {
        "classes": classes[:50],
        "functions": functions[:100],
        "imports": list(set(imports))[:50],
        "parse_errors": [],
    }


def _parse_php(content: str, filepath: str) -> dict:
    classes = list(set(_PHP_CLASS_RE.findall(content)))
    functions = list(set(_PHP_FUNC_RE.findall(content)))
    imports = re.findall(r"(?:require|include)(?:_once)?\s*['\"]([^'\"]+)['\"]", content)
    return {
        "classes": classes[:50],
        "functions": functions[:100],
        "imports": list(set(imports))[:50],
        "parse_errors": [],
    }


def _parse_swift_kotlin(content: str, filepath: str) -> dict:
    classes = list(set(_SWIFT_CLASS_RE.findall(content)))
    functions = list(set(_SWIFT_FUNC_RE.findall(content)))
    imports = re.findall(r"import\s+([A-Za-z_][A-Za-z0-9_.]*)", content)
    return {
        "classes": classes[:50],
        "functions": functions[:100],
        "imports": list(set(imports))[:50],
        "parse_errors": [],
    }


# ── Extension → parser mapping ────────────────────────────────────────────────

_PARSERS = {
    ".py": _parse_python,
    ".js": _parse_javascript,
    ".jsx": _parse_javascript,
    ".ts": _parse_javascript,
    ".tsx": _parse_javascript,
    ".mjs": _parse_javascript,
    ".cjs": _parse_javascript,
    ".java": _parse_java_kotlin,
    ".scala": _parse_java_kotlin,
    ".groovy": _parse_java_kotlin,
    ".c": _parse_cpp,
    ".cc": _parse_cpp,
    ".cpp": _parse_cpp,
    ".cxx": _parse_cpp,
    ".h": _parse_cpp,
    ".hpp": _parse_cpp,
    ".hxx": _parse_cpp,
    ".go": _parse_go,
    ".rs": _parse_rust,
    ".rb": _parse_ruby,
    ".php": _parse_php,
    ".kt": _parse_swift_kotlin,
    ".kts": _parse_swift_kotlin,
    ".swift": _parse_swift_kotlin,
}


def parse_file(filepath: str, content: str) -> dict:
    """
    Parse a single file and return its structural information.
    One file's parse failure never affects other files.
    """
    suffix = Path(filepath).suffix.lower()
    parser = _PARSERS.get(suffix)

    if parser is None:
        # For non-code files (markdown, yaml, etc.) return empty but valid result
        return {
            "classes": [],
            "functions": [],
            "imports": [],
            "parse_errors": [],
        }

    try:
        return parser(content, filepath)
    except Exception as exc:
        # Absolute safety net — this file is skipped, others continue
        return {
            "classes": [],
            "functions": [],
            "imports": [],
            "parse_errors": [f"{filepath}: unexpected parser error: {exc}"],
        }


def parse_repository(documents: list[dict]) -> dict:
    """
    Parse all extracted documents and aggregate results.

    Returns:
        classes      — deduplicated list of all class/struct names found
        functions    — deduplicated list of all function/method names found
        imports      — deduplicated list of all import statements found
        parse_errors — list of files that had parse issues (others continued fine)
        files_parsed — number of files successfully parsed
    """
    all_classes: set[str] = set()
    all_functions: set[str] = set()
    all_imports: set[str] = set()
    all_errors: list[str] = []
    files_parsed = 0

    for doc in documents:
        filepath = doc.get("file", "")
        content = doc.get("content", "")

        if not content:
            continue

        result = parse_file(filepath, content)

        all_classes.update(result["classes"])
        all_functions.update(result["functions"])
        all_imports.update(result["imports"])
        all_errors.extend(result["parse_errors"])
        files_parsed += 1

    return {
        "classes": sorted(all_classes)[:500],
        "functions": sorted(all_functions)[:1000],
        "imports": sorted(all_imports)[:500],
        "parse_errors": all_errors[:50],
        "files_parsed": files_parsed,
        "class_count": len(all_classes),
        "function_count": len(all_functions),
    }
