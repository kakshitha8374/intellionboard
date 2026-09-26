import { useEffect, useMemo, useRef, useState } from "react";
import "./App.css";

import {
  Activity,
  ArrowLeft,
  ArrowRight,
  BookOpenCheck,
  Brain,
  Bug,
  CheckCircle2,
  ChevronRight,
  Code2,
  FileCode2,
  GitBranch,
  GitCommit,
  History,
  Layers3,
  Lightbulb,
  LogOut,
  MessageSquare,
  Network,
  Search,
  Send,
  Sparkles,
  Target,
  TestTube2,
  UserRound,
  Zap,
} from "lucide-react";

const API_URL = "http://127.0.0.1:8000";
const STORAGE_KEY = "intellonboardd_user";
const REPO_KEY = "intellonboardd_repo";
const REPO_URL_KEY = "intellonboardd_repo_url";

// ============================================================
// GITHUB ICON (inline SVG — avoids lucide-react version mismatches)
// ============================================================

function GithubIcon({ size = 16, style, ...props }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      style={style}
      {...props}
    >
      <path d="M12 .5C5.73.5.5 5.75.5 12.09c0 5.08 3.29 9.39 7.86 10.91.58.11.79-.25.79-.56 0-.28-.01-1.02-.02-2-3.2.7-3.88-1.55-3.88-1.55-.52-1.33-1.28-1.69-1.28-1.69-1.04-.71.08-.7.08-.7 1.15.08 1.76 1.19 1.76 1.19 1.03 1.76 2.69 1.25 3.35.96.1-.74.4-1.25.73-1.54-2.55-.29-5.23-1.28-5.23-5.71 0-1.26.45-2.29 1.18-3.09-.12-.29-.51-1.47.11-3.06 0 0 .96-.31 3.15 1.18a10.9 10.9 0 0 1 2.87-.39c.97 0 1.95.13 2.87.39 2.19-1.49 3.15-1.18 3.15-1.18.62 1.59.23 2.77.11 3.06.73.8 1.18 1.83 1.18 3.09 0 4.44-2.69 5.42-5.25 5.7.41.36.78 1.07.78 2.16 0 1.56-.01 2.81-.01 3.19 0 .31.21.68.8.56A10.98 10.98 0 0 0 23.5 12.09C23.5 5.75 18.27.5 12 .5Z" />
    </svg>
  );
}

// ============================================================
// 10 FEATURES DEFINITION
// ============================================================

const FEATURES = [
  {
    id: "brain",
    number: "01",
    title: "Repository Brain",
    shortTitle: "Repository Brain",
    description:
      "Ask questions about architecture, setup, modules, files and implementation details.",
    icon: Brain,
    color: "#f97316",
  },
  {
    id: "architecture",
    number: "02",
    title: "Architecture Explorer",
    shortTitle: "Architecture",
    description:
      "Explore modules, files, classes, functions and dependency relationships.",
    icon: Network,
    color: "#3b82f6",
  },
  {
    id: "time-machine",
    number: "03",
    title: "Codebase Time Machine",
    shortTitle: "Git History",
    description:
      "Understand how the repository evolved through commits and file history.",
    icon: History,
    color: "#8b5cf6",
  },
  {
    id: "impact",
    number: "04",
    title: "Change Impact Simulator",
    shortTitle: "Change Impact",
    description:
      "Understand which parts of the codebase may be affected by a change.",
    icon: Activity,
    color: "#ec4899",
  },
  {
    id: "contribution",
    number: "05",
    title: "First Contribution Generator",
    shortTitle: "First Contribution",
    description:
      "Find beginner-friendly contribution opportunities inside the repository.",
    icon: Lightbulb,
    color: "#f59e0b",
  },
  {
    id: "onboarding",
    number: "06",
    title: "Adaptive Onboarding",
    shortTitle: "Onboarding",
    description:
      "Generate a personalized onboarding path based on your developer role.",
    icon: Target,
    color: "#10b981",
  },
  {
    id: "mentor",
    number: "07",
    title: "AI Developer Mentor",
    shortTitle: "AI Mentor",
    description:
      "Ask an AI mentor questions while learning an unfamiliar codebase.",
    icon: UserRound,
    color: "#6366f1",
  },
  {
    id: "documentation",
    number: "08",
    title: "Documentation Drift Detector",
    shortTitle: "Documentation Drift",
    description:
      "Detect documentation that may no longer match the actual codebase.",
    icon: BookOpenCheck,
    color: "#14b8a6",
  },
  {
    id: "bug",
    number: "09",
    title: "AI Bug Investigation",
    shortTitle: "Bug Investigation",
    description:
      "Investigate bugs using repository code, history and supporting evidence.",
    icon: Bug,
    color: "#ef4444",
  },
  {
    id: "test-gap",
    number: "10",
    title: "Test Gap & Test Generator",
    shortTitle: "Test Gap",
    description: "Find potential testing gaps and generate suggested tests.",
    icon: TestTube2,
    color: "#0ea5e9",
  },
];

// ============================================================
// HELPERS
// ============================================================

function getRepoName(url) {
  if (!url) return "";
  let value = url.trim().replace(/\/+$/, "");
  if (value.endsWith(".git")) value = value.slice(0, -4);
  return value.split("/").pop() || "";
}

function safeArray(value) {
  return Array.isArray(value) ? value : [];
}

function formatNumber(value) {
  const number = Number(value || 0);
  if (Number.isNaN(number)) return "0";
  return number.toLocaleString();
}

function getNodeType(node) {
  const type = String(
    node?.type || node?.kind || node?.category || node?.node_type || ""
  ).toLowerCase();
  if (type.includes("class")) return "class";
  if (type.includes("function") || type.includes("method")) return "function";
  if (type.includes("file") || type.includes("module")) return "file";
  return type || "file";
}

function getNodeName(node) {
  return node?.name || node?.label || node?.id || node?.path || "Unnamed node";
}

function getNodePath(node) {
  return node?.path || node?.file || node?.filepath || node?.module || "";
}

function normalizeGraphData(data) {
  const rawNodes = safeArray(
    data?.nodes || data?.graph?.nodes || data?.knowledge_graph?.nodes
  );
  const rawEdges = safeArray(
    data?.edges ||
      data?.links ||
      data?.graph?.edges ||
      data?.knowledge_graph?.edges
  );

  const nodes = rawNodes.map((node, index) => ({
    ...node,
    id: node?.id || node?.name || node?.path || `node-${index}`,
    name: getNodeName(node),
    path: getNodePath(node),
    type: getNodeType(node),
  }));

  const edges = rawEdges.map((edge, index) => ({
    ...edge,
    id: edge?.id || `edge-${index}`,
    source: edge?.source || edge?.from || edge?.source_id || "",
    target: edge?.target || edge?.to || edge?.target_id || "",
    type: edge?.type || edge?.relationship || edge?.kind || "depends on",
  }));

  return { nodes, edges };
}

// ============================================================
// MAIN APP
// ============================================================

// ── Scroll to top helper ─────────────────────────────────────────────────────
function scrollToTop() {
  window.scrollTo({ top: 0, behavior: "instant" });
}

export default function App() {
  const [page, setPage] = useState("login");
  const [user, setUser] = useState(null);
  const [repoUrl, setRepoUrl] = useState("");
  const [repoName, setRepoName] = useState("");
  const [analysisData, setAnalysisData] = useState(null);
  const [selectedFeature, setSelectedFeature] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  // Job-based analysis progress
  const [analysisStage, setAnalysisStage] = useState("");
  const [analysisStageNum, setAnalysisStageNum] = useState(0);
  const [analysisElapsed, setAnalysisElapsed] = useState(0);
  const pollRef = useRef(null);

  // Scroll to top whenever the page changes
  useEffect(() => {
    scrollToTop();
  }, [page]);

  useEffect(() => {
    try {
      const savedUser = localStorage.getItem(STORAGE_KEY);
      const savedRepo = localStorage.getItem(REPO_KEY);
      const savedRepoUrl = localStorage.getItem(REPO_URL_KEY);
      if (savedUser) {
        const parsed = JSON.parse(savedUser);
        setTimeout(() => {
          setUser(parsed);
          if (savedRepo && savedRepoUrl) {
            setRepoName(savedRepo);
            setRepoUrl(savedRepoUrl);
            // On session restore, fetch (or re-fetch) the analysis result.
            // Without this, analysisData stays null after a page refresh and
            // every metric card shows 0.
            fetch(`${API_URL}/analyze`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ repo_url: savedRepoUrl }),
            })
              .then((r) => r.json())
              .then((data) => {
                if (data && (data.from_cache || data.scan || data.code_structure)) {
                  // Cached result — populate dashboard immediately
                  setAnalysisData(data);
                  setPage("dashboard");
                } else if (data && data.job_id) {
                  // Backend started a new analysis job (cache was missing).
                  // Show the repository page with live progress, then navigate
                  // to dashboard when the job completes so metrics are correct.
                  setLoading(true);
                  setMessage("Re-indexing repository...");
                  setPage("repository");
                  const jobId = data.job_id;
                  const STAGE_LABELS = [
                    "",
                    "Step 1/5 — Cloning repository...",
                    "Step 2/5 — Scanning source files...",
                    "Step 3/5 — Parsing code structure...",
                    "Step 4/5 — Analyzing Git history...",
                    "Step 5/5 — Building AI index...",
                  ];
                  const MAX_RESTORE_POLL_MS = 25 * 60 * 1000;
                  const restorePollStart = Date.now();
                  const poll = setInterval(async () => {
                    if (Date.now() - restorePollStart > MAX_RESTORE_POLL_MS) {
                      clearInterval(poll);
                      setLoading(false);
                      setError("Analysis is taking too long. Please re-submit the repository URL.");
                      setPage("repository");
                      return;
                    }
                    try {
                      const sr = await fetch(`${API_URL}/analyze/status/${jobId}`);
                      const sd = await sr.json();
                      setAnalysisStageNum(sd.stage_num || 0);
                      setAnalysisElapsed(sd.elapsed_seconds || 0);
                      setAnalysisStage(STAGE_LABELS[sd.stage_num] || sd.stage || "");
                      if (sd.status === "failed") {
                        clearInterval(poll);
                        setLoading(false);
                        setError(sd.error || "Analysis failed.");
                        setPage("repository");
                      } else if (sd.status === "completed") {
                        clearInterval(poll);
                        const rr = await fetch(`${API_URL}/analyze/result/${jobId}`);
                        const rd = await rr.json();
                        setAnalysisData(rd);
                        setMessage("Repository analyzed successfully!");
                        setAnalysisStage("Step 5/5 — Complete!");
                        setAnalysisStageNum(5);
                        setLoading(false);
                        setPage("dashboard");
                      }
                    } catch {
                      clearInterval(poll);
                      setLoading(false);
                    }
                  }, 2000);
                  pollRef.current = poll;
                } else {
                  // Unknown response — go to dashboard anyway (may show zeros)
                  setPage("dashboard");
                }
              })
              .catch(() => {
                // Network error — go to dashboard; metrics may be zero but
                // the user can re-analyze from the repository page
                setPage("dashboard");
              });
          } else if (savedRepo) {
            // Have repo name but no saved URL — cannot fetch live metrics.
            // Send the user to the repository page so they can re-submit the
            // URL (one click) rather than landing on a dashboard of zeros.
            setRepoName(savedRepo);
            setPage("repository");
          } else {
            setPage("repository");
          }
        }, 0);
      }
    } catch {
      // ignore corrupted storage
    }
  }, []);

  function handleLogin(email) {
    const newUser = { name: email.split("@")[0], email };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(newUser));
    setUser(newUser);
    setPage("repository");
    setError("");
  }

  function handleSignup(name, email) {
    const newUser = { name, email };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(newUser));
    setUser(newUser);
    setPage("repository");
    setError("");
  }

  function handleLogout() {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(REPO_KEY);
    localStorage.removeItem(REPO_URL_KEY);
    setUser(null);
    setRepoUrl("");
    setRepoName("");
    setAnalysisData(null);
    setSelectedFeature(null);
    if (pollRef.current) clearInterval(pollRef.current);
    setPage("login");
  }

  async function handleAnalyze(event) {
    event.preventDefault();
    setError("");
    setMessage("");
    setAnalysisStage("");
    setAnalysisStageNum(0);
    setAnalysisElapsed(0);

    if (!repoUrl.trim()) {
      setError("Please enter a GitHub repository URL.");
      return;
    }

    const extractedRepo = getRepoName(repoUrl);
    if (!extractedRepo) {
      setError("Please enter a valid GitHub repository URL.");
      return;
    }

    setLoading(true);
    setMessage("Starting repository analysis...");
    setAnalysisStage("Step 1/5 — Connecting to repository...");
    setAnalysisStageNum(1);

    try {
      const response = await fetch(`${API_URL}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: repoUrl.trim() }),
      });

      const data = await response.json();

      if (!response.ok || data?.status === "error") {
        throw new Error(data?.message || "Repository analysis failed.");
      }

      // ── Cached result returned synchronously ─────────────────────────
      if (data?.from_cache || !data?.job_id) {
        const finalRepo = data?.repository || extractedRepo;
        setRepoName(finalRepo);
        localStorage.setItem(REPO_KEY, finalRepo);
        localStorage.setItem(REPO_URL_KEY, repoUrl.trim());
        setAnalysisData(data);
        setMessage("Repository loaded from cache!");
        setAnalysisStage("Loaded from cache");
        setAnalysisStageNum(5);
        setLoading(false);
        setPage("dashboard");
        return;
      }

      // ── Job-based: poll for real progress ────────────────────────────
      const jobId = data.job_id;
      const finalRepo = data?.repository || extractedRepo;
      setRepoName(finalRepo);
      localStorage.setItem(REPO_KEY, finalRepo);
      localStorage.setItem(REPO_URL_KEY, repoUrl.trim());

      const STAGE_LABELS = [
        "",
        "Step 1/5 — Cloning repository...",
        "Step 2/5 — Scanning source files...",
        "Step 3/5 — Parsing code structure...",
        "Step 4/5 — Analyzing Git history...",
        "Step 5/5 — Building AI index...",
      ];

      // Maximum time the frontend will wait for any single analysis job.
      // Backend per-stage timeouts sum to ~20 min max; we give 25 min here
      // so the UI always stops before the backend could theoretically hang.
      const MAX_POLL_MS = 25 * 60 * 1000; // 25 minutes
      const pollStart = Date.now();

      await new Promise((resolve, reject) => {
        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = setInterval(async () => {
          // Hard client-side deadline — never poll forever
          if (Date.now() - pollStart > MAX_POLL_MS) {
            clearInterval(pollRef.current);
            reject(new Error(
              "Analysis is taking too long (>25 min). " +
              "The repository may be too large or the server encountered a problem. " +
              "Please try again."
            ));
            return;
          }

          try {
            const statusRes = await fetch(`${API_URL}/analyze/status/${jobId}`);
            if (!statusRes.ok) {
              clearInterval(pollRef.current);
              reject(new Error(`Status check failed: HTTP ${statusRes.status}`));
              return;
            }
            const statusData = await statusRes.json();
            const stageNum = statusData.stage_num || 0;
            setAnalysisStageNum(stageNum);
            setAnalysisElapsed(statusData.elapsed_seconds || 0);
            setAnalysisStage(STAGE_LABELS[stageNum] || statusData.stage || "");

            if (statusData.status === "failed") {
              clearInterval(pollRef.current);
              // Surface the exact backend error to the user
              reject(new Error(statusData.error || "Repository analysis failed."));
            } else if (statusData.status === "completed") {
              clearInterval(pollRef.current);
              const resultRes = await fetch(`${API_URL}/analyze/result/${jobId}`);
              const resultData = await resultRes.json();
              resolve(resultData);
            }
            // else: still running — keep polling
          } catch (pollErr) {
            clearInterval(pollRef.current);
            reject(pollErr);
          }
        }, 2000); // Poll every 2 seconds
      }).then((resultData) => {
        setAnalysisData(resultData);
        setMessage("Repository analyzed successfully!");
        setAnalysisStage("Step 5/5 — Complete!");
        setAnalysisStageNum(5);
        setLoading(false);
        setPage("dashboard");
      });

    } catch (err) {
      setError(err?.message || "Unable to analyze repository.");
      setLoading(false);
    }
  }

  function openFeature(feature) {
    setSelectedFeature(feature);

    if (feature.id === "brain") { setPage("brain"); return; }
    if (feature.id === "architecture") { setPage("architecture"); return; }
    if (feature.id === "time-machine") { setPage("time-machine"); return; }
    if (feature.id === "mentor") { setPage("mentor"); return; }

    setPage("feature-detail");
  }

  if (!user) {
    if (page === "signup") {
      return <SignupPage onSignup={handleSignup} onLogin={() => setPage("login")} />;
    }
    return <LoginPage onLogin={handleLogin} onSignup={() => setPage("signup")} />;
  }

  return (
    <div className="app-shell">
      <TopBar user={user} repoName={repoName} onLogout={handleLogout} />

      {page === "repository" && (
        <RepositoryPage
          repoUrl={repoUrl}
          setRepoUrl={setRepoUrl}
          loading={loading}
          message={message}
          error={error}
          onAnalyze={handleAnalyze}
          analysisStage={analysisStage}
          analysisStageNum={analysisStageNum}
          analysisElapsed={analysisElapsed}
        />
      )}

      {page === "dashboard" && (
        <DashboardPage
          repoName={repoName}
          analysisData={analysisData}
          onFeature={openFeature}
        />
      )}

      {page === "brain" && (
        <BrainPage repoName={repoName} onBack={() => setPage("dashboard")} />
      )}

      {page === "architecture" && (
        <ArchitectureExplorer repoName={repoName} onBack={() => setPage("dashboard")} />
      )}

      {page === "time-machine" && (
        <TimeMachinePage repoName={repoName} onBack={() => setPage("dashboard")} />
      )}

      {page === "mentor" && (
        <MentorPage repoName={repoName} onBack={() => setPage("dashboard")} />
      )}

      {page === "feature-detail" && (
        <FeatureDetailPage
          feature={selectedFeature}
          repoName={repoName}
          onBack={() => setPage("dashboard")}
        />
      )}
    </div>
  );
}

// ============================================================
// TOP BAR
// ============================================================

function TopBar({ user, repoName, onLogout }) {
  return (
    <header className="topbar">
      <div className="brand">
        <div className="brand-mark">
          <Sparkles size={18} />
        </div>
        <span>IntelliOnboard</span>
      </div>

      <div className="topbar-right">
        {repoName && (
          <div className="repo-pill">
            <GithubIcon size={13} />
            {repoName}
          </div>
        )}
        {repoName && (
          <div className="repo-pill" style={{ background: "#ecfdf3", border: "1px solid #abefc6", color: "#027a48" }}>
            <CheckCircle2 size={13} />
            Analyzed
          </div>
        )}
        <div className="user-email">{user?.name || user?.email}</div>
        <button className="ghost-button" onClick={onLogout}>
          <LogOut size={13} style={{ marginRight: 5 }} />
          Logout
        </button>
      </div>
    </header>
  );
}

// ============================================================
// LOGIN PAGE
// ============================================================

function LoginPage({ onLogin, onSignup }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  function submit(event) {
    event.preventDefault();
    if (!email.trim()) return;
    onLogin(email.trim());
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <div className="brand-mark">
            <Sparkles size={18} />
          </div>
          IntelliOnboard
        </div>

        <h1 className="auth-title">Welcome back</h1>
        <p className="auth-description">
          AI-powered developer onboarding and repository intelligence.
        </p>

        <form className="auth-form" onSubmit={submit}>
          <div className="form-group">
            <label className="form-label">Email</label>
            <input
              className="form-input"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <label className="form-label">Password</label>
            <input
              className="form-input"
              type="password"
              placeholder="Enter password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <button className="auth-submit" type="submit">
            Sign In
          </button>
        </form>

        <div className="auth-switch">
          Don&apos;t have an account?{" "}
          <button onClick={onSignup}>Sign up free</button>
        </div>

        <div className="auth-features">
          {["Repository Brain", "Architecture Explorer", "AI Mentor", "10 AI Features"].map((f) => (
            <div key={f} className="auth-feature-item">
              <CheckCircle2 size={13} style={{ color: "#f97316" }} />
              {f}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ============================================================
// SIGNUP PAGE
// ============================================================

function SignupPage({ onSignup, onLogin }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  function submit(event) {
    event.preventDefault();
    if (!name.trim() || !email.trim()) return;
    onSignup(name.trim(), email.trim());
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <div className="brand-mark">
            <Sparkles size={18} />
          </div>
          IntelliOnboard
        </div>

        <h1 className="auth-title">Create account</h1>
        <p className="auth-description">
          Start understanding any codebase in minutes.
        </p>

        <form className="auth-form" onSubmit={submit}>
          <div className="form-group">
            <label className="form-label">Name</label>
            <input
              className="form-input"
              type="text"
              placeholder="Your name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <label className="form-label">Email</label>
            <input
              className="form-input"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <label className="form-label">Password</label>
            <input
              className="form-input"
              type="password"
              placeholder="Create password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <button className="auth-submit" type="submit">
            Create Account
          </button>
        </form>

        <div className="auth-switch">
          Already have an account? <button onClick={onLogin}>Sign in</button>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// REPOSITORY PAGE
// ============================================================

function RepositoryPage({ repoUrl, setRepoUrl, loading, message, error, onAnalyze, analysisStage, analysisStageNum, analysisElapsed }) {
  const TOTAL_STAGES = 5;
  // Determinate progress bar width based on stage
  const progressPct = analysisStageNum > 0 ? Math.round((analysisStageNum / TOTAL_STAGES) * 100) : null;

  return (
    <main className="detail-page">
      <div className="page-container">
        <div style={{ maxWidth: 820, margin: "60px auto" }}>
          <div className="eyebrow" style={{ justifyContent: "center" }}>
            <GithubIcon size={14} />
            STEP 1 · CONNECT REPOSITORY
          </div>

          <h1 style={{ textAlign: "center", fontSize: "clamp(36px, 5vw, 56px)", lineHeight: 1.08, margin: "0 0 16px", letterSpacing: -2, fontWeight: 800 }}>
            Connect your{" "}
            <span style={{ color: "#f97316" }}>codebase.</span>
          </h1>

          <p style={{ textAlign: "center", maxWidth: 600, margin: "0 auto 40px", color: "#667085", fontSize: 16, lineHeight: 1.7 }}>
            Enter a public GitHub repository URL. IntelliOnboard will clone,
            analyze and index the repository for AI-powered insights.
          </p>

          <div className="connect-card">
            <div className="section-eyebrow">GitHub Repository URL</div>
            <h2 className="connect-title">Analyze your repository</h2>
            <p className="connect-description">
              Paste any public GitHub repository URL below to get started.
            </p>

            <form className="analyze-form" onSubmit={onAnalyze}>
              <input
                className="repo-input"
                type="text"
                placeholder="https://github.com/psf/requests"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                disabled={loading}
              />
              <button className="primary-button" type="submit" disabled={loading}>
                {loading ? (
                  <>
                    <div className="btn-spinner" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    Analyze Repository
                    <ArrowRight size={15} />
                  </>
                )}
              </button>
            </form>

            {loading && (
              <div className="progress-bar-wrap">
                {/* Progress bar — determinate when stage is known */}
                <div className="progress-bar-track">
                  {progressPct !== null ? (
                    <div
                      className="progress-bar-fill-determinate"
                      style={{ width: `${progressPct}%` }}
                    />
                  ) : (
                    <div className="progress-bar-fill" />
                  )}
                </div>
                {/* Stage label */}
                {analysisStage && (
                  <div style={{ fontSize: 13, fontWeight: 600, color: "#1a1f2b", marginTop: 10 }}>
                    {analysisStage}
                  </div>
                )}
                {analysisElapsed > 0 && (
                  <div style={{ fontSize: 12, color: "#667085", marginTop: 4 }}>
                    Elapsed: {analysisElapsed}s — Large repositories may take a few minutes.
                  </div>
                )}
              </div>
            )}

            {message && !error && !loading && (
              <div className="status-message status-success">
                <CheckCircle2 size={14} style={{ marginRight: 6 }} />
                {message}
              </div>
            )}

            {error && (
              <div className="status-message status-error">{error}</div>
            )}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginTop: 18 }}>
            {[
              { icon: <Brain size={17} />, title: "Repository Brain", text: "Ask anything about the code" },
              { icon: <Network size={17} />, title: "Architecture Map", text: "Explore code structure" },
              { icon: <History size={17} />, title: "Git Time Machine", text: "Understand code evolution" },
            ].map(({ icon, title, text }) => (
              <div key={title} style={{ background: "white", border: "1px solid #e5e7eb", borderRadius: 14, padding: 18 }}>
                <div className="feature-icon">{icon}</div>
                <div style={{ marginTop: 10, fontWeight: 700, fontSize: 13 }}>{title}</div>
                <div style={{ marginTop: 3, fontSize: 12, color: "#667085" }}>{text}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}

// ============================================================
// DASHBOARD
// ============================================================

function DashboardPage({ repoName, analysisData, onFeature }) {
  // Derive metrics directly from analysisData (code_structure) — no extra API call needed
  const metrics = useMemo(() => {
    // Prefer real code_structure data from analysis (produced by code_parser)
    const codeStructure = analysisData?.code_structure;
    const scanData = analysisData?.scan;

    console.log("ANALYSIS RESULT:", analysisData);
    console.log("CODE STRUCTURE:", codeStructure);
    console.log("SCAN DATA:", scanData);

    const classes = codeStructure?.class_count ?? 0;
    const functions = codeStructure?.function_count ?? 0;
    const files = scanData?.file_count ?? scanData?.files_analyzed ?? 0;

    let commits = 0;
    const history = analysisData?.git_history;
    if (Array.isArray(history)) commits = history.length;
    else if (Array.isArray(history?.commits)) commits = history.commits.length;
    else if (Number.isFinite(Number(history?.commit_count))) commits = Number(history.commit_count);

    console.log("METRICS COMPUTED:", { files, functions, classes, commits });
    return { files, functions, classes, commits };
  }, [analysisData]);

  return (
    <main className="detail-page">
      <div className="page-container">
        {/* Hero */}
        <section className="hero">
          <div className="hero-grid">
            <div>
              <div className="eyebrow">
                <Sparkles size={13} />
                AI Developer Onboarding Platform
              </div>
              <h1>
                Understand any codebase.
                <br />
                <span>Start contributing faster.</span>
              </h1>
              <p className="hero-description">
                IntelliOnboard uses AI to turn an unfamiliar repository into a
                clear, navigable developer experience.
              </p>
            </div>
            <div className="hero-side-card">
              <div className="hero-side-label">Active Repository</div>
              <div className="hero-side-repo">{repoName}</div>
              <div className="hero-side-text">
                Repository indexed and ready for AI-powered exploration across
                all 10 features.
              </div>
              <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
                <div style={{ background: "rgba(249,115,22,0.2)", color: "#fdba74", fontSize: 11, fontWeight: 700, padding: "4px 10px", borderRadius: 999 }}>
                  <CheckCircle2 size={11} style={{ marginRight: 4 }} />
                  Analyzed
                </div>
                <div style={{ background: "rgba(255,255,255,0.1)", color: "#b7bcc7", fontSize: 11, fontWeight: 700, padding: "4px 10px", borderRadius: 999 }}>
                  10 Features Ready
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Metrics — sourced from code_structure in analysisData (real parse results) */}
        <section className="metrics-grid">
          <MetricCard icon={<FileCode2 size={17} />} value={formatNumber(metrics.files)} label="Files Indexed" />
          <MetricCard icon={<Code2 size={17} />} value={formatNumber(metrics.functions)} label="Functions" />
          <MetricCard icon={<Layers3 size={17} />} value={formatNumber(metrics.classes)} label="Classes" />
          <MetricCard icon={<GitCommit size={17} />} value={formatNumber(metrics.commits)} label="Commits" />
        </section>

        {/* 10 Features — single grid, no duplicates */}
        <section className="features-section">
          <div className="section-header">
            <div className="section-eyebrow">INTELLIONBOARD TOOLKIT</div>
            <h2>10 AI-powered features.</h2>
            <p>Everything you need to understand, contribute to, and navigate any repository.</p>
          </div>

          <div className="features-grid">
            {FEATURES.map((feature) => (
              <FeatureCard key={feature.id} feature={feature} onClick={() => onFeature(feature)} />
            ))}
          </div>
        </section>
      </div>

      <footer className="app-footer">
        IntelliOnboard · AI-powered developer onboarding · {repoName && <strong>{repoName}</strong>}
      </footer>
    </main>
  );
}

function MetricCard({ icon, value, label }) {
  return (
    <div className="metric-card">
      <div className="metric-icon">{icon}</div>
      <div className="metric-value">{value}</div>
      <div className="metric-label">{label}</div>
    </div>
  );
}

function FeatureCard({ feature, onClick }) {
  const Icon = feature.icon;
  return (
    <button className="feature-card" onClick={onClick}>
      <div className="feature-icon" style={{ background: `${feature.color}15`, color: feature.color }}>
        <Icon size={19} />
      </div>
      <div className="feature-number">FEATURE {feature.number}</div>
      <div className="feature-title">{feature.title}</div>
      <div className="feature-description">{feature.description}</div>
      <div className="feature-action">
        Open <ChevronRight size={13} />
      </div>
    </button>
  );
}

// ============================================================
// SHARED: PAGE SHELL
// ============================================================

function PageShell({ title, description, icon, featureNumber, repoName, onBack, children }) {
  const Icon = icon;
  return (
    <main className="detail-page">
      <div className="page-container" style={{ maxWidth: 900 }}>
        <button className="back-button" onClick={onBack}>
          <ArrowLeft size={14} />
          Back to Dashboard
        </button>

        <div className="page-header">
          <div className="page-header-icon">
            <Icon size={22} />
          </div>
          <div>
            {featureNumber && (
              <div className="section-eyebrow" style={{ marginBottom: 4 }}>FEATURE {featureNumber}</div>
            )}
            <h1 className="detail-title" style={{ margin: 0 }}>{title}</h1>
            <p className="detail-description" style={{ marginTop: 6 }}>
              {description}{repoName && <> · <strong>{repoName}</strong></>}
            </p>
          </div>
        </div>

        {children}
      </div>
    </main>
  );
}

// ============================================================
// FEATURE 1: REPOSITORY BRAIN
// ============================================================

function BrainPage({ repoName, onBack }) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [brainData, setBrainData] = useState(null);
  const [brainLoading, setBrainLoading] = useState(true);

  useEffect(() => {
    async function loadBrain() {
      try {
        const res = await fetch(`${API_URL}/brain/${encodeURIComponent(repoName)}`);
        if (res.ok) {
          const data = await res.json();
          setBrainData(data);
        }
      } catch {
        // ignore
      } finally {
        setBrainLoading(false);
      }
    }
    if (repoName) loadBrain();
  }, [repoName]);

  async function askQuestion(event) {
    event.preventDefault();
    if (!question.trim()) return;

    setLoading(true);
    setAnswer("");
    setSources([]);
    setError("");

    try {
      const res = await fetch(`${API_URL}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question.trim(), repo_name: repoName }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.message || "Unable to answer.");
      setAnswer(data?.answer || "No answer returned.");
      setSources(safeArray(data?.sources));
    } catch (err) {
      setError(err?.message || "Repository Brain failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <PageShell
      title="Repository Brain"
      description="Ask anything about this repository"
      icon={Brain}
      featureNumber="01"
      repoName={repoName}
      onBack={onBack}
    >
      {/* Auto-loaded overview */}
      {brainLoading ? (
        <div className="result-card">
          <div className="loading-state">
            <div className="loading-spinner" />
            Loading repository overview...
          </div>
        </div>
      ) : brainData?.summary ? (
        <div className="result-card" style={{ marginBottom: 24 }}>
          <div className="result-label">
            <Brain size={13} />
            Repository Overview
          </div>
          <div className="result-text">{brainData.summary}</div>

          {brainData.important_files?.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <div style={{ fontSize: 11, fontWeight: 800, color: "#667085", letterSpacing: 0.4, marginBottom: 8 }}>
                KEY FILES ({brainData.file_count} total)
              </div>
              <div className="file-list">
                {brainData.important_files.slice(0, 12).map((f, i) => (
                  <span key={i} className="file-tag">{f}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : null}

      {/* Ask anything */}
      <div className="result-card">
        <div className="result-label">
          <Search size={13} />
          Ask a Question
        </div>
        <form onSubmit={askQuestion}>
          <div className="brain-search">
            <Search size={15} style={{ color: "#9ca3af", flexShrink: 0 }} />
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="How does authentication work in this repo?"
            />
            <button className="primary-button" type="submit" disabled={loading} style={{ minHeight: 36, padding: "8px 16px", fontSize: 13 }}>
              {loading ? <><div className="btn-spinner" />Thinking...</> : <>Ask <Send size={13} /></>}
            </button>
          </div>
        </form>

        {error && <div className="status-message status-error" style={{ marginTop: 14 }}>{error}</div>}

        {answer && (
          <div style={{ marginTop: 18 }}>
            <div style={{ fontSize: 11, fontWeight: 800, color: "#f97316", letterSpacing: 0.4, marginBottom: 8 }}>AI ANSWER</div>
            <div className="ai-answer-text">{answer}</div>
          </div>
        )}

        {sources.length > 0 && (
          <div style={{ marginTop: 18 }}>
            <div style={{ fontSize: 11, fontWeight: 800, color: "#667085", letterSpacing: 0.4, marginBottom: 8 }}>
              SOURCES ({sources.length})
            </div>
            {sources.map((source, i) => (
              <div key={i} className="source-row">
                <FileCode2 size={13} style={{ color: "#f97316", flexShrink: 0 }} />
                <span>{source?.file || source?.path || `Source ${i + 1}`}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </PageShell>
  );
}

// ============================================================
// FEATURE 2: ARCHITECTURE EXPLORER
// ============================================================

function ArchitectureExplorer({ repoName, onBack }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("files");
  const [search, setSearch] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch(`${API_URL}/graph/${encodeURIComponent(repoName)}`);
        const result = await res.json();
        if (!res.ok) throw new Error(result?.message || "Unable to load architecture.");
        if (!cancelled) setData(normalizeGraphData(result));
      } catch (err) {
        if (!cancelled) setError(err?.message || "Unable to load architecture.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    if (repoName) {
      load();
    } else {
      setTimeout(() => {
        setLoading(false);
        setError("No repository selected.");
      }, 0);
    }
    return () => { cancelled = true; };
  }, [repoName]);

  const nodes = useMemo(() => data?.nodes || [], [data]);
  const edges = useMemo(() => data?.edges || [], [data]);
  const files = useMemo(() => nodes.filter((n) => n.type === "file"), [nodes]);
  const classes = useMemo(() => nodes.filter((n) => n.type === "class"), [nodes]);
  const functions = useMemo(() => nodes.filter((n) => n.type === "function"), [nodes]);

  const filteredNodes = useMemo(() => {
    const q = search.toLowerCase();
    const pool = tab === "files" ? files : tab === "classes" ? classes : tab === "functions" ? functions : nodes;
    return q ? pool.filter((n) => String(n.name).toLowerCase().includes(q) || String(n.path).toLowerCase().includes(q)) : pool;
  }, [nodes, files, classes, functions, tab, search]);

  const tabs = [
    ["files", "Files", files.length],
    ["classes", "Classes", classes.length],
    ["functions", "Functions", functions.length],
    ["deps", "Dependencies", edges.length],
  ];

  return (
    <PageShell
      title="Architecture Explorer"
      description="Explore code structure and dependencies"
      icon={Network}
      featureNumber="02"
      repoName={repoName}
      onBack={onBack}
    >
      {loading ? (
        <div className="result-card">
          <div className="loading-state"><div className="loading-spinner" />Loading architecture...</div>
        </div>
      ) : error ? (
        <div className="status-message status-error">{error}</div>
      ) : (
        <>
          {/* Metrics */}
          <div className="arch-metrics">
            {[
              { label: "Total Files", value: nodes.length },
              { label: "Dependencies", value: edges.length },
              { label: "Classes", value: classes.length },
              { label: "Functions", value: functions.length },
            ].map(({ label, value }) => (
              <div key={label} className="arch-metric">
                <div className="arch-metric-value">{formatNumber(value)}</div>
                <div className="arch-metric-label">{label}</div>
              </div>
            ))}
          </div>

          {/* Tab panel */}
          <div className="result-card" style={{ padding: 0, overflow: "hidden" }}>
            <div className="arch-tabs">
              {tabs.map(([id, label, count]) => (
                <button key={id} className={`arch-tab${tab === id ? " active" : ""}`} onClick={() => setTab(id)}>
                  {label} <span className="tab-count">{count}</span>
                </button>
              ))}
            </div>

            {tab !== "deps" && (
              <div style={{ padding: "12px 18px 0" }}>
                <div className="architecture-search">
                  <Search size={14} style={{ color: "#9ca3af" }} />
                  <input placeholder="Search..." value={search} onChange={(e) => setSearch(e.target.value)} />
                </div>
              </div>
            )}

            <div style={{ maxHeight: 440, overflowY: "auto", padding: "14px 18px 18px" }}>
              {tab === "deps" ? (
                edges.length === 0 ? (
                  <EmptyState icon={<GitBranch size={18} />} title="No dependencies" text="No dependency edges found." />
                ) : (
                  edges.slice(0, 80).map((edge) => (
                    <div key={edge.id} className="dependency-row">
                      <span className="dep-source">{edge.source?.split("/").pop()}</span>
                      <span className="dep-arrow">→</span>
                      <span className="dep-target">{edge.target?.split("/").pop()}</span>
                      <span className="dep-type">{edge.type}</span>
                    </div>
                  ))
                )
              ) : filteredNodes.length === 0 ? (
                <EmptyState icon={<Search size={18} />} title="No results" text="Try a different search." />
              ) : (
                filteredNodes.slice(0, 100).map((node) => (
                  <div key={node.id} className="arch-node">
                    <div className="arch-node-icon">
                      {node.type === "class" ? <Layers3 size={13} /> : node.type === "function" ? <Code2 size={13} /> : <FileCode2 size={13} />}
                    </div>
                    <div>
                      <div className="arch-node-name">{node.name}</div>
                      {node.path && <div className="arch-node-path">{node.path}</div>}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </PageShell>
  );
}

// ============================================================
// FEATURE 3: CODEBASE TIME MACHINE
// ============================================================

function TimeMachinePage({ repoName, onBack }) {
  const [commits, setCommits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedCommit, setSelectedCommit] = useState(null);
  const [diff, setDiff] = useState("");
  const [diffLoading, setDiffLoading] = useState(false);
  const [fileQuery, setFileQuery] = useState("");
  const [fileHistory, setFileHistory] = useState([]);
  const [fileLoading, setFileLoading] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`${API_URL}/time-machine/${encodeURIComponent(repoName)}/commits`);
        const data = await res.json();
        if (!res.ok) throw new Error(data?.message || "Unable to load commits.");
        setCommits(safeArray(data?.commits));
      } catch (err) {
        setError(err?.message || "Unable to load commits.");
      } finally {
        setLoading(false);
      }
    }
    if (repoName) load();
  }, [repoName]);

  async function loadDiff(commit) {
    setSelectedCommit(commit);
    setDiff("");
    setDiffLoading(true);
    try {
      const res = await fetch(`${API_URL}/time-machine/${encodeURIComponent(repoName)}/diff?commit=${encodeURIComponent(commit.commit)}`);
      const data = await res.json();
      setDiff(data?.diff || "No diff available.");
    } catch {
      setDiff("Unable to load diff.");
    } finally {
      setDiffLoading(false);
    }
  }

  async function loadFileHistory(event) {
    event.preventDefault();
    if (!fileQuery.trim()) return;
    setFileLoading(true);
    setFileHistory([]);
    try {
      const res = await fetch(`${API_URL}/time-machine/${encodeURIComponent(repoName)}/file?file=${encodeURIComponent(fileQuery.trim())}`);
      const data = await res.json();
      setFileHistory(safeArray(data?.history));
    } catch {
      setFileHistory([]);
    } finally {
      setFileLoading(false);
    }
  }

  return (
    <PageShell
      title="Codebase Time Machine"
      description="Explore commit history and file changes"
      icon={History}
      featureNumber="03"
      repoName={repoName}
      onBack={onBack}
    >
      {loading ? (
        <div className="result-card"><div className="loading-state"><div className="loading-spinner" />Loading commits...</div></div>
      ) : error ? (
        <div className="status-message status-error">{error}</div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          {/* Commit list */}
          <div className="result-card" style={{ padding: 0, overflow: "hidden" }}>
            <div style={{ padding: "16px 18px 12px", borderBottom: "1px solid #f0f0f0" }}>
              <div className="result-label" style={{ marginBottom: 0 }}>
                <GitCommit size={13} />
                Recent Commits ({commits.length})
              </div>
            </div>
            <div style={{ maxHeight: 420, overflowY: "auto" }}>
              {commits.length === 0 ? (
                <EmptyState icon={<History size={18} />} title="No commits" text="No commit history found." />
              ) : commits.map((commit) => (
                <div
                  key={commit.commit}
                  className={`commit-row${selectedCommit?.commit === commit.commit ? " selected" : ""}`}
                  onClick={() => loadDiff(commit)}
                >
                  <div className="commit-hash">{commit.commit?.slice(0, 7)}</div>
                  <div className="commit-message">{commit.message}</div>
                  <div className="commit-meta">{commit.author} · {commit.date}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Right side: diff + file history */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {/* Diff viewer */}
            <div className="result-card">
              <div className="result-label"><GitBranch size={13} />Commit Diff</div>
              {diffLoading ? (
                <div style={{ textAlign: "center", padding: 20 }}><div className="loading-spinner" style={{ margin: "0 auto" }} /></div>
              ) : diff ? (
                <pre className="diff-viewer">{diff}</pre>
              ) : (
                <div style={{ color: "#9ca3af", fontSize: 13, padding: "8px 0" }}>Click a commit to view its diff.</div>
              )}
            </div>

            {/* File history */}
            <div className="result-card">
              <div className="result-label"><History size={13} />File History</div>
              <form onSubmit={loadFileHistory} style={{ display: "flex", gap: 8, marginBottom: 12 }}>
                <input
                  className="form-input"
                  style={{ padding: "8px 12px", fontSize: 13 }}
                  placeholder="src/requests/auth.py"
                  value={fileQuery}
                  onChange={(e) => setFileQuery(e.target.value)}
                />
                <button className="primary-button" type="submit" disabled={fileLoading} style={{ padding: "8px 14px", fontSize: 13 }}>
                  {fileLoading ? "..." : "Search"}
                </button>
              </form>
              {fileHistory.length > 0 ? (
                fileHistory.slice(0, 8).map((h, i) => (
                  <div key={i} className="commit-row" style={{ marginBottom: 4 }}>
                    <div className="commit-hash">{h.commit?.slice(0, 7)}</div>
                    <div className="commit-message">{h.message}</div>
                    <div className="commit-meta">{h.date}</div>
                  </div>
                ))
              ) : (
                <div style={{ color: "#9ca3af", fontSize: 13 }}>Enter a file path to see its history.</div>
              )}
            </div>
          </div>
        </div>
      )}
    </PageShell>
  );
}

// ============================================================
// FEATURE 7: AI DEVELOPER MENTOR (dedicated chat)
// ============================================================

function MentorPage({ repoName, onBack }) {
  const [messages, setMessages] = useState([
    { role: "assistant", text: `Hello! I'm your AI mentor for **${repoName}**. Ask me anything about this codebase — architecture, how to get started, how a specific feature works, or what to look at next.` }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [skillLevel, setSkillLevel] = useState("beginner");
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function sendMessage(event) {
    event.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: userMessage }]);
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/mentor/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_name: repoName, question: userMessage, skill_level: skillLevel }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.message || "Mentor failed.");
      setMessages((prev) => [...prev, { role: "assistant", text: data?.answer || "No answer." }]);
    } catch (err) {
      setMessages((prev) => [...prev, { role: "error", text: err?.message || "Unable to get response." }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <PageShell
      title="AI Developer Mentor"
      description="Chat with an AI mentor about this codebase"
      icon={MessageSquare}
      featureNumber="07"
      repoName={repoName}
      onBack={onBack}
    >
      {/* Skill level selector */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        {["beginner", "intermediate", "advanced"].map((level) => (
          <button
            key={level}
            onClick={() => setSkillLevel(level)}
            className={`skill-btn${skillLevel === level ? " active" : ""}`}
          >
            {level.charAt(0).toUpperCase() + level.slice(1)}
          </button>
        ))}
        <span style={{ fontSize: 12, color: "#9ca3af", alignSelf: "center", marginLeft: 8 }}>
          Mentor adapts responses to your level
        </span>
      </div>

      {/* Chat */}
      <div className="chat-container">
        <div className="chat-messages">
          {messages.map((msg, i) => (
            <div key={i} className={`chat-message chat-${msg.role}`}>
              {msg.role === "assistant" && (
                <div className="chat-avatar">
                  <UserRound size={14} />
                </div>
              )}
              <div className={`chat-bubble chat-bubble-${msg.role}`}>
                {msg.text}
              </div>
            </div>
          ))}
          {loading && (
            <div className="chat-message chat-assistant">
              <div className="chat-avatar"><UserRound size={14} /></div>
              <div className="chat-bubble chat-bubble-assistant">
                <div className="typing-dots">
                  <span /><span /><span />
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <form className="chat-input-bar" onSubmit={sendMessage}>
          <input
            className="chat-input"
            placeholder="Ask your mentor anything about the codebase..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
          />
          <button className="primary-button" type="submit" disabled={loading || !input.trim()} style={{ padding: "10px 18px" }}>
            <Send size={15} />
          </button>
        </form>
      </div>
    </PageShell>
  );
}

// ============================================================
// FEATURE DETAIL PAGE (handles features 4,5,6,8,9,10)
// ============================================================

function FeatureDetailPage({ feature, repoName, onBack }) {
  const Icon = feature?.icon || Sparkles;
  const [input, setInput] = useState("");
  const [role, setRole] = useState("beginner");
  const [file, setFile] = useState("");
  const [generateTests, setGenerateTests] = useState(false);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function runFeature() {
    setLoading(true);
    setResult(null);
    setError("");

    try {
      let endpoint = "";
      let body = {};
      let method = "POST";

      switch (feature.id) {
        case "impact":
          endpoint = `/impact/${encodeURIComponent(repoName)}`;
          body = { query: input || "Show the impact of changing a core module." };
          break;

        case "contribution":
          endpoint = "/first-contribution";
          body = { repo_name: repoName, skill_level: role };
          break;

        case "onboarding":
          endpoint = "/onboarding/plan";
          body = { repo_name: repoName, role };
          break;

        case "documentation":
          endpoint = "/documentation/drift";
          body = { repo_name: repoName };
          break;

        case "bug":
          endpoint = "/bug-investigation";
          body = {
            repo_name: repoName,
            bug_description: input || "Investigate unexpected behavior in the repository.",
            skill_level: role,
          };
          break;

        case "test-gap":
          endpoint = "/test-gap";
          body = {
            repo_name: repoName,
            file: file || "",
            skill_level: role,
            generate_tests: generateTests,
          };
          break;

        default:
          endpoint = "";
      }

      if (!endpoint) {
        setResult({ message: "Feature ready." });
        setLoading(false);
        return;
      }

      const res = await fetch(`${API_URL}${endpoint}`, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const data = await res.json();
      if (!res.ok || data?.status === "error") {
        throw new Error(data?.message || "Feature failed.");
      }

      setResult(data);
    } catch (err) {
      setError(err?.message || "Unable to run feature.");
    } finally {
      setLoading(false);
    }
  }

  const needsInput = ["impact", "bug"].includes(feature?.id);
  const needsRole = ["contribution", "onboarding", "bug", "test-gap"].includes(feature?.id);
  const isTestGap = feature?.id === "test-gap";

  const inputPlaceholders = {
    impact: "Describe the change you want to simulate (e.g. 'refactor authentication module')...",
    bug: "Describe the bug you want to investigate...",
  };

  // Extract the main AI text from the result
  function getMainText(data) {
    if (!data) return null;
    return data?.impact_analysis || data?.suggestions || data?.onboarding_plan ||
      data?.drift_analysis || data?.investigation || data?.gap_analysis || null;
  }

  function getFiles(data) {
    if (!data) return [];
    return safeArray(
      data?.potentially_affected_files || data?.relevant_files ||
      data?.documentation_files_checked || []
    );
  }

  return (
    <PageShell
      title={feature.title}
      description={feature.description}
      icon={Icon}
      featureNumber={feature.number}
      repoName={repoName}
      onBack={onBack}
    >
      <div className="result-card">
        {needsInput && (
          <div className="form-group" style={{ marginBottom: 16 }}>
            <label className="form-label">{feature.id === "bug" ? "Bug Description" : "Change Description"}</label>
            <textarea
              className="form-input"
              style={{ minHeight: 100, padding: 12, resize: "vertical" }}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={inputPlaceholders[feature.id] || "Enter description..."}
            />
          </div>
        )}

        {isTestGap && (
          <div className="form-group" style={{ marginBottom: 16 }}>
            <label className="form-label">Target File (optional)</label>
            <input
              className="form-input"
              placeholder="src/requests/auth.py"
              value={file}
              onChange={(e) => setFile(e.target.value)}
            />
          </div>
        )}

        {needsRole && (
          <div className="form-group" style={{ marginBottom: 16 }}>
            <label className="form-label">
              {feature.id === "onboarding" ? "Developer Role" : "Skill Level"}
            </label>
            <select className="form-input" value={role} onChange={(e) => setRole(e.target.value)}>
              {feature.id === "onboarding" ? (
                <>
                  <option value="beginner">Beginner Developer</option>
                  <option value="backend">Backend Developer</option>
                  <option value="frontend">Frontend Developer</option>
                  <option value="data scientist">Data Scientist / ML Engineer</option>
                </>
              ) : (
                <>
                  <option value="beginner">Beginner</option>
                  <option value="intermediate">Intermediate</option>
                  <option value="advanced">Advanced</option>
                </>
              )}
            </select>
          </div>
        )}

        {isTestGap && (
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
            <input
              type="checkbox"
              id="gen-tests"
              checked={generateTests}
              onChange={(e) => setGenerateTests(e.target.checked)}
              style={{ width: 16, height: 16 }}
            />
            <label htmlFor="gen-tests" style={{ fontSize: 13.5, fontWeight: 600, cursor: "pointer" }}>
              Also generate test code examples
            </label>
          </div>
        )}

        <button className="primary-button" onClick={runFeature} disabled={loading}>
          {loading ? (
            <><div className="btn-spinner" />Analyzing with AI...</>
          ) : (
            <><Zap size={15} />Run {feature.shortTitle}</>
          )}
        </button>
      </div>

      {error && <div className="status-message status-error" style={{ marginTop: 16 }}>{error}</div>}

      {result && (
        <div className="result-card" style={{ marginTop: 16 }}>
          <div className="result-label">
            <CheckCircle2 size={13} />
            {feature.title} — Results
          </div>

          {/* Main AI text */}
          {getMainText(result) && (
            <div className="ai-answer-text" style={{ marginBottom: 16 }}>
              {getMainText(result)}
            </div>
          )}

          {/* Affected / relevant files */}
          {getFiles(result).length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 11, fontWeight: 800, color: "#667085", letterSpacing: 0.4, marginBottom: 8 }}>
                RELEVANT FILES
              </div>
              <div className="file-list">
                {getFiles(result).map((f, i) => (
                  <span key={i} className="file-tag">{f}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </PageShell>
  );
}

// ============================================================
// EMPTY STATE
// ============================================================

function EmptyState({ icon, title, text }) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon">{icon}</div>
      <div className="empty-state-title">{title}</div>
      <div className="empty-state-text">{text}</div>
    </div>
  );
}
