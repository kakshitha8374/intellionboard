"""
IntelliOnboard API — main.py

Key improvements:
  - /analyze now returns a job_id immediately (non-blocking for large repos)
  - GET /analyze/status/{job_id} — real progress stages
  - GET /analyze/result/{job_id} — completed result
  - Code parser integrated: real classes/functions/commits from analysis
  - Analysis results cached per repo HEAD commit
  - /graph returns real class/function nodes from code parser
  - All subprocess calls have timeouts
  - Documents payload NOT returned in responses (would be huge for TF)
  - Per-stage wall-clock timeouts — no stage can hang forever
  - Stage-level logging with elapsed time
  - Embeddings/vector-store skipped for basic metric analysis
  - Guaranteed job terminal state (completed or failed) always set
"""

import logging
import threading
import time
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from services.github_ingestion import clone_repository
from services.repo_scanner import scan_repository
from services.file_extractor import extract_files
from services.code_parser import parse_repository
from services.git_history import get_git_history, format_git_history
from services.chunker import chunk_documents
from services.vector_store import store_chunks
from services.retriever import search_repository
from services.llm_service import generate_answer
from services.analysis_cache import (
    load_cache, save_cache,
    get_ai_cache, set_ai_cache,
)
from services.onboarding_service import (
    generate_onboarding_prompt,
    normalize_role,
)


app = FastAPI(title="IntelliOnboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# IN-MEMORY JOB STORE
# ============================================================

# job_id → { status, stage, stage_num, total_stages, result, error, started_at }
_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()


def _get_job(job_id: str) -> dict:
    with _JOBS_LOCK:
        return dict(_JOBS.get(job_id, {}))


def _update_job(job_id: str, **kwargs) -> None:
    with _JOBS_LOCK:
        if job_id in _JOBS:
            _JOBS[job_id].update(kwargs)


def _create_job() -> str:
    job_id = str(uuid.uuid4())
    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "status": "pending",
            "stage": "Queued",
            "stage_num": 0,
            "total_stages": 5,
            "result": None,
            "error": None,
            "started_at": time.time(),
        }
    return job_id


# ============================================================
# REQUEST MODELS
# ============================================================

class AnalyzeRequest(BaseModel):
    repo_url: str


class AskRequest(BaseModel):
    question: str
    repo_name: str


class OnboardingRequest(BaseModel):
    role: str
    repo_name: str


class OnboardingPlanRequest(BaseModel):
    repo_name: str
    role: str


class OnboardingFollowupRequest(BaseModel):
    repo_name: str
    role: str
    question: str


class ImpactRequest(BaseModel):
    query: str


class ContributionRequest(BaseModel):
    repo_name: str
    skill_level: Optional[str] = "beginner"


class MentorAskRequest(BaseModel):
    repo_name: str
    question: str
    skill_level: Optional[str] = "beginner"
    session_id: Optional[str] = None


class DocumentationDriftRequest(BaseModel):
    repo_name: str


class BugInvestigationRequest(BaseModel):
    repo_name: str
    bug_description: str
    skill_level: Optional[str] = "intermediate"


class TestGapRequest(BaseModel):
    repo_name: str
    file: Optional[str] = ""
    skill_level: Optional[str] = "intermediate"
    generate_tests: Optional[bool] = False


# ============================================================
# HEALTH
# ============================================================

@app.get("/")
def root():
    return {"message": "IntelliOnboard backend is running!"}


@app.get("/health")
def health():
    return {"status": "healthy"}


# ============================================================
# CORE ANALYSIS WORKER
# ============================================================

# Per-stage time budgets (seconds).  Each stage is run in a daemon thread;
# if it exceeds its budget the job is marked failed immediately and the
# frontend stops polling.
_STAGE_TIMEOUTS = {
    "clone":   660,   # 11 min — Kubernetes shallow clone is ~2 GB
    "scan":     90,   # 90 s  — rglob already has its own 60 s internal cut-off
    "extract":  90,   # 90 s  — same walk, same cut-off
    "parse":   120,   # 2 min — pure CPU regex / AST on ≤2000 files
    "git":      60,   # 60 s  — git log is bounded
    "embed":   300,   # 5 min — sentence-transformer on ≤16 k chunks
}

# Logger used inside the analysis worker (shows up in uvicorn output)
_log = logging.getLogger("intellionboard.analysis")


def _stage(job_id: str, label: str, num: int, detail: str = "") -> float:
    """Update job stage and return the current monotonic time (stage start)."""
    msg = label if not detail else f"{label} ({detail})"
    _update_job(job_id, stage=msg, stage_num=num)
    _log.info("[job:%s] stage %d — %s", job_id[:8], num, msg)
    return time.monotonic()


def _elapsed(t0: float) -> str:
    return f"{time.monotonic() - t0:.1f}s"


def _run_in_thread(fn, timeout: int, *args, **kwargs):
    """
    Run *fn* in a daemon thread with a hard wall-clock timeout.

    Returns (result, None) on success or (None, error_string) on failure/timeout.
    The result is whatever *fn* returns; exceptions are caught and stringified.
    """
    result_box: list = [None]
    error_box:  list = [None]

    def _wrapper():
        try:
            result_box[0] = fn(*args, **kwargs)
        except Exception as exc:
            error_box[0] = str(exc)

    t = threading.Thread(target=_wrapper, daemon=True)
    t.start()
    t.join(timeout)

    if t.is_alive():
        # Thread is still running — we cannot kill it, but we stop waiting.
        # Return a timeout error; the thread will eventually finish on its own.
        return None, (
            f"Stage timed out after {timeout}s. "
            "The repository may be too large for this machine. "
            "Try a smaller repository or increase the timeout."
        )
    if error_box[0] is not None:
        return None, error_box[0]
    return result_box[0], None


def _run_analysis(job_id: str, repo_url: str, repo_name: str) -> None:
    """
    Background thread that runs the full repository analysis pipeline.

    Stages:
      1/5 — Cloning repository         (bounded: CLONE_TIMEOUT)
      2/5 — Scanning source files      (bounded: SCAN_WALK_TIMEOUT + stage timeout)
      3/5 — Parsing code structure     (bounded: stage timeout)
      4/5 — Analyzing Git history      (bounded: GIT_TIMEOUT)
      5/5 — Building AI index          (bounded: embed timeout; skipped for huge repos)

    Guarantees:
      - Job ALWAYS reaches status=completed or status=failed — never stays running.
      - Every stage logs start time, end time, and number of items processed.
      - Embedding / vector-store is run in a separate bounded thread so it cannot
        block the metrics result from being returned.
    """
    job_start = time.monotonic()
    repo_path = f"repos/{repo_name}"

    # Outer safety net: no matter what happens, job gets a terminal state.
    try:
        _update_job(job_id, status="running")

        # ── Stage 1: Clone ──────────────────────────────────────────────────
        t0 = _stage(job_id, "Cloning repository...", 1)
        clone_result, err = _run_in_thread(
            clone_repository, _STAGE_TIMEOUTS["clone"],
            repo_url, repo_name,
        )
        if err:
            raise RuntimeError(f"Clone failed: {err}")
        repo_path = clone_result["path"]
        _log.info("[job:%s] clone done in %s — path=%s status=%s",
                  job_id[:8], _elapsed(t0), repo_path, clone_result.get("status"))

        # ── Check cache ─────────────────────────────────────────────────────
        cached = load_cache("full_analysis", repo_path)
        if cached:
            _log.info("[job:%s] loaded from cache in %s total", job_id[:8], _elapsed(job_start))
            _update_job(job_id, status="completed", stage="Loaded from cache",
                        stage_num=5, result=cached)
            return

        # ── Stage 2: Scan ───────────────────────────────────────────────────
        t0 = _stage(job_id, "Scanning source files...", 2)
        scan_result, err = _run_in_thread(
            scan_repository, _STAGE_TIMEOUTS["scan"],
            repo_path,
        )
        if err:
            raise RuntimeError(f"Scan failed: {err}")

        files_found    = scan_result.get("file_count", 0)
        files_analyzed = scan_result.get("files_analyzed", 0)
        _log.info("[job:%s] scan done in %s — found=%d analyzed=%d walk_timeout=%s",
                  job_id[:8], _elapsed(t0), files_found, files_analyzed,
                  scan_result.get("walk_timed_out", False))
        _stage(job_id, "Scanning source files...", 2,
               f"{files_found} files found, {files_analyzed} to analyze")

        if files_found == 0 and files_analyzed == 0:
            raise RuntimeError(
                f"No supported source files were found in '{repo_name}'. "
                f"Skip reasons: {scan_result.get('skip_reasons', {})}. "
                "This may indicate an incomplete clone or an unsupported repository structure."
            )

        # ── Stage 3: Extract + Parse code structure ─────────────────────────
        # Pass the already-scanned file list so extract_files skips its own
        # rglob walk — cuts stage-3 time on large repos like Kubernetes from
        # ~60 s down to < 5 s (only reads file content, no directory walk).
        pre_scanned = scan_result.get("files")  # list[str] of relative paths
        t0 = _stage(job_id, "Parsing code structure...", 3,
                    f"extracting up to {files_analyzed} files")
        documents, err = _run_in_thread(
            extract_files, _STAGE_TIMEOUTS["extract"],
            repo_path, pre_scanned,
        )
        if err:
            raise RuntimeError(f"File extraction failed: {err}")
        _log.info("[job:%s] extract done in %s — %d documents",
                  job_id[:8], _elapsed(t0), len(documents))

        t0 = _stage(job_id, "Parsing code structure...", 3,
                    f"parsing {len(documents)} files")
        parse_result, err = _run_in_thread(
            parse_repository, _STAGE_TIMEOUTS["parse"],
            documents,
        )
        if err:
            raise RuntimeError(f"Code parsing failed: {err}")
        _log.info("[job:%s] parse done in %s — classes=%d functions=%d errors=%d",
                  job_id[:8], _elapsed(t0),
                  parse_result.get("class_count", 0),
                  parse_result.get("function_count", 0),
                  len(parse_result.get("parse_errors", [])))

        # ── Stage 4: Git history ────────────────────────────────────────────
        t0 = _stage(job_id, "Analyzing Git history...", 4)
        git_history, err = _run_in_thread(
            get_git_history, _STAGE_TIMEOUTS["git"],
            repo_path, 30,
        )
        if err:
            # Git history failure is non-fatal — metrics still work without it
            _log.warning("[job:%s] git history failed: %s", job_id[:8], err)
            git_history = {"status": "error", "message": err,
                           "commit_count": 0, "commits": []}
        else:
            _log.info("[job:%s] git done in %s — commits=%d status=%s",
                      job_id[:8], _elapsed(t0),
                      git_history.get("commit_count", 0),
                      git_history.get("status"))

        commit_count = git_history.get("commit_count", 0)

        # ── Assemble core result (metrics ready — save now before embeddings) ─
        result = {
            "message": "Repository analyzed successfully",
            "repository": repo_name,
            "clone": clone_result,
            "scan": {
                "file_count": files_found,
                "files_analyzed": files_analyzed,
                "files_skipped": scan_result.get("files_skipped", 0),
                "extensions": scan_result.get("extensions", {}),
                "skip_reasons": scan_result.get("skip_reasons", {}),
                "total_source_kb": scan_result.get("total_source_kb", 0),
                "walk_timed_out": scan_result.get("walk_timed_out", False),
                "files": scan_result.get("files", [])[:100],
            },
            "code_structure": {
                "class_count": parse_result.get("class_count", 0),
                "function_count": parse_result.get("function_count", 0),
                "classes": parse_result.get("classes", [])[:100],
                "functions": parse_result.get("functions", [])[:200],
                "imports": parse_result.get("imports", [])[:100],
                "files_parsed": parse_result.get("files_parsed", 0),
                "parse_errors_count": len(parse_result.get("parse_errors", [])),
            },
            "git_history": git_history,
            "vector_store": {"status": "pending"},
            "chunks_indexed": 0,
            "_diagnostics": {
                "files_found": files_found,
                "files_analyzed": files_analyzed,
                "documents_extracted": len(documents),
                "chunks_created": 0,
                "commits_found": commit_count,
                "git_status": git_history.get("status"),
                "parse_errors": parse_result.get("parse_errors", [])[:10],
                "total_elapsed_s": round(time.monotonic() - job_start, 1),
            },
        }

        # ── Stage 5: Build AI index (embeddings) ────────────────────────────
        # This is the SLOWEST stage (sentence-transformer on CPU).
        # We run it in a bounded thread.  If it times out or fails we still
        # mark the job completed with the core metrics — the AI features
        # (Brain, Mentor, etc.) just won't have search results yet.
        t0 = _stage(job_id, "Building AI index...", 5,
                    f"embedding {len(documents)} documents")
        chunks = chunk_documents(documents)
        _log.info("[job:%s] chunked %d docs → %d chunks", job_id[:8], len(documents), len(chunks))

        vector_result, embed_err = _run_in_thread(
            store_chunks, _STAGE_TIMEOUTS["embed"],
            chunks, repo_name,
        )
        if embed_err:
            _log.warning("[job:%s] embedding failed/timed-out: %s", job_id[:8], embed_err)
            result["vector_store"] = {"status": "error", "message": embed_err}
            result["_diagnostics"]["embed_error"] = embed_err
        else:
            _log.info("[job:%s] embedding done in %s", job_id[:8], _elapsed(t0))
            result["vector_store"] = vector_result or {"status": "success"}
            result["chunks_indexed"] = len(chunks)
            result["_diagnostics"]["chunks_created"] = len(chunks)

        # ── Cache and complete ───────────────────────────────────────────────
        save_cache("full_analysis", repo_path, result)

        total = round(time.monotonic() - job_start, 1)
        stage_msg = f"Analysis complete ({files_analyzed} files, {commit_count} commits)"
        _log.info("[job:%s] COMPLETE in %ss", job_id[:8], total)
        result["_diagnostics"]["total_elapsed_s"] = total
        _update_job(job_id, status="completed", stage=stage_msg, stage_num=5, result=result)

    except Exception as exc:
        total = round(time.monotonic() - job_start, 1)
        err_msg = str(exc)
        _log.error("[job:%s] FAILED after %ss: %s", job_id[:8], total, err_msg)
        # Guaranteed terminal state — frontend polling always stops here
        _update_job(job_id, status="failed", error=err_msg)


# ============================================================
# ANALYZE — non-blocking job-based API
# ============================================================

@app.post("/analyze")
def analyze_repository(request: AnalyzeRequest):
    """
    Start repository analysis. Returns job_id immediately.
    Poll GET /analyze/status/{job_id} for progress.
    GET /analyze/result/{job_id} for the completed result.

    Also supports synchronous mode for backwards compatibility:
    if the repo was already analyzed (cached), returns the result directly.
    """
    from services.analysis_cache import clear_repo_cache

    repo_url = request.repo_url.rstrip("/")
    repo_name = repo_url.split("/")[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    # Check if already cloned + cached — return synchronously for instant response
    # load_cache now returns None for broken/empty repos, so this is always safe.
    repo_path = f"repos/{repo_name}"
    cached = load_cache("full_analysis", repo_path)
    if cached:
        return {
            **cached,
            "job_id": None,
            "from_cache": True,
        }

    # Start background analysis
    job_id = _create_job()

    thread = threading.Thread(
        target=_run_analysis,
        args=(job_id, repo_url, repo_name),
        daemon=True,
    )
    thread.start()

    return {
        "message": "Repository analysis started",
        "repository": repo_name,
        "job_id": job_id,
        "status": "running",
        "poll_url": f"/analyze/status/{job_id}",
        "result_url": f"/analyze/result/{job_id}",
    }


@app.get("/analyze/status/{job_id}")
def get_analyze_status(job_id: str):
    """Return real-time progress of a repository analysis job."""
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    elapsed = round(time.time() - job.get("started_at", time.time()), 1)

    return {
        "job_id": job_id,
        "status": job.get("status"),
        "stage": job.get("stage"),
        "stage_num": job.get("stage_num"),
        "total_stages": job.get("total_stages"),
        "elapsed_seconds": elapsed,
        "error": job.get("error"),
    }


@app.get("/analyze/result/{job_id}")
def get_analyze_result(job_id: str):
    """Return the completed analysis result for a job."""
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.get("status") == "failed":
        raise HTTPException(status_code=500, detail=job.get("error", "Analysis failed"))

    if job.get("status") != "completed":
        return {
            "job_id": job_id,
            "status": job.get("status"),
            "stage": job.get("stage"),
            "stage_num": job.get("stage_num"),
            "message": "Analysis still in progress. Poll /analyze/status/{job_id}.",
        }

    return job.get("result", {})


# ============================================================
# ASK (Repository Brain basic)
# ============================================================

@app.post("/ask")
def ask_repository(request: AskRequest):
    results = search_repository(request.question, request.repo_name)

    context_parts = []
    for result in results:
        context_parts.append(
            f"File: {result['file']}\nChunk: {result['content']}"
        )
    code_context = "\n\n".join(context_parts)

    repo_path = f"repos/{request.repo_name}"
    git_history = get_git_history(repo_path, max_commits=10)
    history_context = format_git_history(git_history)

    context = f"REPOSITORY CODE:\n\n{code_context}\n\nGIT HISTORY:\n\n{history_context}"

    # Check AI cache
    cached_answer = get_ai_cache("ask", request.repo_name, context + request.question)
    if cached_answer:
        answer = cached_answer
    else:
        answer = generate_answer(request.question, context)
        set_ai_cache("ask", request.repo_name, context + request.question, answer)

    return {
        "question": request.question,
        "repository": request.repo_name,
        "answer": answer,
        "sources": results,
        "git_history": git_history,
    }


# ============================================================
# REPOSITORY BRAIN (Feature 1)
# ============================================================

@app.get("/brain/{repo_name}")
def get_brain(repo_name: str):
    repo_path = f"repos/{repo_name}"

    # Load cached analysis for structural stats (no LLM needed for stats)
    cached_analysis = load_cache("full_analysis", repo_path)

    results = search_repository(
        "project purpose architecture important files technologies modules overview",
        repo_name,
        top_k=5,
    )

    context_parts = []
    for result in results:
        context_parts.append(f"File: {result['file']}\nContent: {result['content']}")
    code_context = "\n\n".join(context_parts)

    git_history = get_git_history(repo_path, max_commits=10)
    history_context = format_git_history(git_history)

    context = f"REPOSITORY CODE:\n\n{code_context}\n\nGIT HISTORY:\n\n{history_context}"

    cached_summary = get_ai_cache("brain_summary", repo_name, code_context)
    if cached_summary:
        summary = cached_summary
    else:
        summary = generate_answer(
            "Give a comprehensive overview: What is this repository? What problem does it solve? "
            "What are the key technologies, modules, and important files? "
            "How is the architecture structured?",
            context,
        )
        set_ai_cache("brain_summary", repo_name, code_context, summary)

    # Use cached scan if available, otherwise do a fresh scan
    if cached_analysis:
        scan = cached_analysis.get("scan", {})
        important_files = scan.get("files", [])[:20]
        file_count = scan.get("file_count", 0)
        extensions = scan.get("extensions", {})
    else:
        scan_result = scan_repository(repo_path)
        important_files = scan_result.get("files", [])[:20]
        file_count = scan_result.get("file_count", 0)
        extensions = scan_result.get("extensions", {})

    return {
        "repository": repo_name,
        "summary": summary,
        "important_files": important_files,
        "file_count": file_count,
        "extensions": extensions,
        "sources": results,
    }


# ============================================================
# KNOWLEDGE GRAPH / ARCHITECTURE (Feature 2)
# ============================================================

@app.get("/graph/{repo_name}")
def get_graph(repo_name: str):
    repo_path = f"repos/{repo_name}"

    # Check cache first
    cached_analysis = load_cache("full_analysis", repo_path)

    if cached_analysis:
        # Use real code structure from the parse result
        code_structure = cached_analysis.get("code_structure", {})
        scan = cached_analysis.get("scan", {})
        files = scan.get("files", [])
        classes = code_structure.get("classes", [])
        functions = code_structure.get("functions", [])
    else:
        # Fallback: scan and parse (no cache available)
        scan_result = scan_repository(repo_path)
        files = scan_result.get("files", [])

        # Parse code to extract real classes/functions
        documents = extract_files(repo_path)
        parse_result = parse_repository(documents)
        classes = parse_result.get("classes", [])
        functions = parse_result.get("functions", [])

    nodes = []
    edges = []

    # File nodes — limit to 500 for graph performance
    for file_path in files[:500]:
        node_id = file_path.replace("\\", "/")
        nodes.append({
            "id": node_id,
            "name": file_path.split("/")[-1].split("\\")[-1],
            "path": file_path,
            "type": "file",
        })

    # Class nodes — real classes from code parser
    for cls_name in classes[:200]:
        node_id = f"class::{cls_name}"
        nodes.append({
            "id": node_id,
            "name": cls_name,
            "path": "",
            "type": "class",
        })

    # Function nodes — real functions from code parser (top 300)
    for fn_name in functions[:300]:
        node_id = f"function::{fn_name}"
        nodes.append({
            "id": node_id,
            "name": fn_name,
            "path": "",
            "type": "function",
        })

    # Build directory-based edges for files in the same module
    dir_map: dict[str, list[str]] = {}
    for node in nodes:
        if node["type"] != "file":
            continue
        parts = node["path"].replace("\\", "/").split("/")
        if len(parts) > 1:
            dir_name = "/".join(parts[:-1])
            if dir_name not in dir_map:
                dir_map[dir_name] = []
            dir_map[dir_name].append(node["id"])

    edge_id = 0
    for dir_name, file_ids in dir_map.items():
        for i, source in enumerate(file_ids):
            for target in file_ids[i + 1 : i + 3]:
                edges.append({
                    "id": f"edge-{edge_id}",
                    "source": source,
                    "target": target,
                    "type": "same-module",
                })
                edge_id += 1

    return {
        "repository": repo_name,
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "class_count": len(classes),
        "function_count": len(functions),
        "file_count": len(files),
    }


# ============================================================
# TIME MACHINE (Feature 3)
# ============================================================

@app.get("/time-machine/{repo_name}/commits")
def get_commits(repo_name: str, limit: int = 30):
    repo_path = f"repos/{repo_name}"
    git_history = get_git_history(repo_path, max_commits=limit)
    return {
        "repository": repo_name,
        "commits": git_history.get("commits", []),
        "commit_count": git_history.get("commit_count", 0),
        "status": git_history.get("status", "unknown"),
    }


@app.get("/time-machine/{repo_name}/file")
def get_file_history(repo_name: str, file: str = ""):
    repo_path = f"repos/{repo_name}"
    import subprocess
    if not file:
        return {"repository": repo_name, "file": file, "history": []}

    command = [
        "git", "-C", repo_path,
        "log", "--pretty=format:%H|%an|%ad|%s",
        "--date=short", "--", file,
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30,
        )
    except Exception:
        return {"repository": repo_name, "file": file, "history": []}

    history = []
    for line in result.stdout.splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4:
            history.append({"commit": parts[0], "author": parts[1], "date": parts[2], "message": parts[3]})

    return {"repository": repo_name, "file": file, "history": history}


@app.get("/time-machine/{repo_name}/diff")
def get_diff(repo_name: str, commit: str = ""):
    repo_path = f"repos/{repo_name}"
    import subprocess
    if not commit:
        return {"repository": repo_name, "commit": commit, "diff": ""}

    command = ["git", "-C", repo_path, "show", "--stat", commit]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30,
        )
    except Exception:
        return {"repository": repo_name, "commit": commit, "diff": "Unable to load diff."}
    return {"repository": repo_name, "commit": commit, "diff": result.stdout[:3000]}


@app.get("/time-machine/{repo_name}/commit/{commit_hash}")
def get_commit_detail(repo_name: str, commit_hash: str):
    repo_path = f"repos/{repo_name}"
    import subprocess
    command = ["git", "-C", repo_path, "show", "--stat", commit_hash]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30,
        )
    except Exception:
        return {"repository": repo_name, "commit": commit_hash, "detail": ""}
    return {"repository": repo_name, "commit": commit_hash, "detail": result.stdout[:3000]}


@app.get("/time-machine/{repo_name}/file-history")
def get_file_history_list(repo_name: str, file: str = ""):
    return get_file_history(repo_name, file)


# ============================================================
# CHANGE IMPACT SIMULATOR (Feature 4)
# ============================================================

@app.post("/impact/{repo_name}")
def get_impact(repo_name: str, request: ImpactRequest):
    query = request.query or "What modules and files would be affected by a core change?"

    results = search_repository(query, repo_name, top_k=6)

    context_parts = []
    for result in results:
        context_parts.append(f"File: {result['file']}\nContent: {result['content']}")
    code_context = "\n\n".join(context_parts)

    cache_key = query[:100]
    cached = get_ai_cache("impact", repo_name, code_context + cache_key)
    if cached:
        impact_answer = cached
    else:
        impact_answer = generate_answer(
            f"Analyze the potential change impact for: '{query}'. "
            "Which files, modules, functions, or classes would likely be affected? "
            "List them with a brief explanation of why each would be impacted.",
            code_context,
        )
        set_ai_cache("impact", repo_name, code_context + cache_key, impact_answer)

    affected_files = list({r["file"] for r in results})

    return {
        "repository": repo_name,
        "query": query,
        "impact_analysis": impact_answer,
        "potentially_affected_files": affected_files,
        "sources": results,
    }


# ============================================================
# FIRST CONTRIBUTION GENERATOR (Feature 5)
# ============================================================

@app.post("/first-contribution")
def first_contribution(request: ContributionRequest):
    skill_level = request.skill_level or "beginner"

    results = search_repository(
        "TODO FIXME simple function utility helper test documentation improvement",
        request.repo_name,
        top_k=5,
    )

    context_parts = []
    for result in results:
        context_parts.append(f"File: {result['file']}\nContent: {result['content']}")
    code_context = "\n\n".join(context_parts)

    cached = get_ai_cache("contribution", request.repo_name, code_context + skill_level)
    if cached:
        suggestions = cached
    else:
        suggestions = generate_answer(
            f"Generate 3 beginner-friendly contribution opportunities for a {skill_level} developer. "
            "For each suggestion: 1) Title of the task, 2) File(s) to modify, "
            "3) What to do (specific steps), 4) Why it's a good first contribution, "
            "5) Expected difficulty level.",
            code_context,
        )
        set_ai_cache("contribution", request.repo_name, code_context + skill_level, suggestions)

    return {
        "repository": request.repo_name,
        "skill_level": skill_level,
        "suggestions": suggestions,
        "relevant_files": [r["file"] for r in results],
    }


# ============================================================
# ADAPTIVE ONBOARDING (Feature 6)
# ============================================================

@app.post("/onboarding")
def create_onboarding_plan_legacy(request: OnboardingRequest):
    role = normalize_role(request.role)
    repo_path = f"repos/{request.repo_name}"
    git_history = get_git_history(repo_path, max_commits=10)
    results = search_repository(
        "project purpose architecture important modules technologies setup",
        request.repo_name,
        top_k=5,
    )

    context_parts = []
    for result in results:
        context_parts.append(f"File: {result['file']}\nContent: {result['content']}")
    repository_context = "\n\n".join(context_parts)
    history_context = format_git_history(git_history)
    prompt = generate_onboarding_prompt(role, repository_context, history_context)

    cached = get_ai_cache("onboarding", request.repo_name, prompt + role)
    if cached:
        answer = cached
    else:
        answer = generate_answer("Create my onboarding plan.", prompt)
        set_ai_cache("onboarding", request.repo_name, prompt + role, answer)

    return {
        "repository": request.repo_name,
        "role": role,
        "onboarding_plan": answer,
    }


@app.post("/onboarding/plan")
def create_onboarding_plan_v2(request: OnboardingPlanRequest):
    role = normalize_role(request.role)
    repo_path = f"repos/{request.repo_name}"
    git_history = get_git_history(repo_path, max_commits=10)

    results = search_repository(
        "project purpose architecture important modules technologies setup",
        request.repo_name,
        top_k=5,
    )

    context_parts = []
    for result in results:
        context_parts.append(f"File: {result['file']}\nContent: {result['content']}")
    repository_context = "\n\n".join(context_parts)
    history_context = format_git_history(git_history)
    prompt = generate_onboarding_prompt(role, repository_context, history_context)

    cached = get_ai_cache("onboarding_plan", request.repo_name, prompt + role)
    if cached:
        answer = cached
    else:
        answer = generate_answer("Create my onboarding plan.", prompt)
        set_ai_cache("onboarding_plan", request.repo_name, prompt + role, answer)

    return {
        "repository": request.repo_name,
        "role": role,
        "onboarding_plan": answer,
    }


@app.post("/onboarding/followup")
def onboarding_followup(request: OnboardingFollowupRequest):
    results = search_repository(request.question, request.repo_name, top_k=3)

    context_parts = []
    for result in results:
        context_parts.append(f"File: {result['file']}\nContent: {result['content']}")
    code_context = "\n\n".join(context_parts)

    answer = generate_answer(
        f"As part of my onboarding as a {request.role}: {request.question}",
        code_context,
    )

    return {
        "repository": request.repo_name,
        "role": request.role,
        "question": request.question,
        "answer": answer,
    }


# ============================================================
# AI DEVELOPER MENTOR (Feature 7)
# ============================================================

@app.post("/mentor/ask")
def mentor_ask(request: MentorAskRequest):
    results = search_repository(request.question, request.repo_name, top_k=4)

    context_parts = []
    for result in results:
        context_parts.append(f"File: {result['file']}\nContent: {result['content']}")
    code_context = "\n\n".join(context_parts)

    repo_path = f"repos/{request.repo_name}"
    git_history = get_git_history(repo_path, max_commits=5)
    history_context = format_git_history(git_history)

    context = f"REPOSITORY CODE:\n\n{code_context}\n\nGIT HISTORY:\n\n{history_context}"

    skill_level = request.skill_level or "intermediate"
    question = (
        f"You are a patient AI mentor. Answer the following question for a {skill_level} developer. "
        f"Be educational, provide examples from the code when available, and suggest what to look at next. "
        f"Question: {request.question}"
    )

    answer = generate_answer(question, context)

    return {
        "repository": request.repo_name,
        "question": request.question,
        "answer": answer,
        "skill_level": skill_level,
        "sources": results,
    }


@app.get("/mentor/sessions")
def get_mentor_sessions():
    return {"sessions": [], "message": "Session history is stored locally."}


# ============================================================
# DOCUMENTATION DRIFT DETECTOR (Feature 8)
# ============================================================

@app.post("/documentation/drift")
def documentation_drift(request: DocumentationDriftRequest):
    doc_results = search_repository(
        "README documentation usage installation API reference changelog",
        request.repo_name,
        top_k=4,
    )

    code_results = search_repository(
        "class function implementation method return type signature",
        request.repo_name,
        top_k=4,
    )

    doc_context = "\n\n".join(
        [f"File: {r['file']}\nContent: {r['content']}" for r in doc_results]
    )
    code_context = "\n\n".join(
        [f"File: {r['file']}\nContent: {r['content']}" for r in code_results]
    )

    context = f"DOCUMENTATION FILES:\n\n{doc_context}\n\nIMPLEMENTATION CODE:\n\n{code_context}"

    cached = get_ai_cache("drift", request.repo_name, doc_context + code_context)
    if cached:
        analysis = cached
    else:
        analysis = generate_answer(
            "Identify documentation drift: Are there any mismatches between what the documentation says "
            "and what the code actually does? Look for: outdated function signatures, missing documentation, "
            "documented features that may no longer exist, or code without documentation. "
            "List each finding with: 1) File, 2) Issue type, 3) Description, 4) Recommendation.",
            context,
        )
        set_ai_cache("drift", request.repo_name, doc_context + code_context, analysis)

    return {
        "repository": request.repo_name,
        "drift_analysis": analysis,
        "documentation_files_checked": [r["file"] for r in doc_results],
        "code_files_checked": [r["file"] for r in code_results],
        "sources": doc_results + code_results,
    }


# ============================================================
# BUG INVESTIGATION (Feature 9)
# ============================================================

@app.post("/bug-investigation")
def bug_investigation(request: BugInvestigationRequest):
    results = search_repository(request.bug_description, request.repo_name, top_k=5)

    context_parts = []
    for result in results:
        context_parts.append(f"File: {result['file']}\nContent: {result['content']}")
    code_context = "\n\n".join(context_parts)

    repo_path = f"repos/{request.repo_name}"
    git_history = get_git_history(repo_path, max_commits=10)
    history_context = format_git_history(git_history)

    context = f"REPOSITORY CODE:\n\n{code_context}\n\nGIT HISTORY:\n\n{history_context}"
    skill_level = request.skill_level or "intermediate"

    investigation = generate_answer(
        f"Investigate the following bug for a {skill_level} developer: '{request.bug_description}'. "
        "Provide: 1) Root cause analysis, 2) Relevant files and code sections, "
        "3) Step-by-step debugging approach, 4) Possible fixes, 5) Prevention recommendations.",
        context,
    )

    return {
        "repository": request.repo_name,
        "bug_description": request.bug_description,
        "investigation": investigation,
        "skill_level": skill_level,
        "relevant_files": [r["file"] for r in results],
        "sources": results,
    }


# ============================================================
# TEST GAP & TEST GENERATION (Feature 10)
# ============================================================

@app.post("/test-gap")
def test_gap(request: TestGapRequest):
    query = f"test coverage gap missing test {request.file}" if request.file else "test coverage missing tests"
    results = search_repository(query, request.repo_name, top_k=5)

    context_parts = []
    for result in results:
        context_parts.append(f"File: {result['file']}\nContent: {result['content']}")
    code_context = "\n\n".join(context_parts)

    skill_level = request.skill_level or "intermediate"
    target_file = request.file or "the codebase"

    question = (
        f"Analyze test coverage gaps for {target_file} at {skill_level} level. "
        "Identify: 1) Functions/methods without tests, 2) Edge cases not covered, "
        "3) Critical paths that need testing. "
        + ("Also generate actual test code examples for the top 3 gaps." if request.generate_tests else "")
    )

    gap_analysis = generate_answer(question, code_context)

    return {
        "repository": request.repo_name,
        "file": request.file,
        "skill_level": skill_level,
        "gap_analysis": gap_analysis,
        "generate_tests": request.generate_tests,
        "relevant_files": [r["file"] for r in results],
        "sources": results,
    }
