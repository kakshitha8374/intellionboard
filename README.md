# IntelliOnboard: AI-Powered Developer Onboarding

IntelliOnboard transforms an unfamiliar GitHub repository into an interactive AI-powered developer guide.

It helps developers understand the codebase, architecture, Git history, documentation, bugs, testing, and contribution opportunities from one platform.

## Problem

Understanding a new software repository can take a lot of time.

Developers often need to:

* Explore thousands of files
* Understand project architecture
* Find important functions and classes
* Study Git history
* Locate bugs and possible causes
* Identify missing tests and documentation
* Find suitable areas for their first contribution

## Solution

IntelliOnboard analyzes a GitHub repository and creates a repository-specific knowledge layer.

The platform combines code analysis, Git history, semantic retrieval, and AI assistance to make repository onboarding easier.

## Key Features

1. **Repository Brain** – Understand the structure and important parts of the repository.
2. **Architecture / Knowledge Graph** – Explore relationships between files, classes, functions, and imports.
3. **Codebase Time Machine** – Explore commits, file history, and code changes.
4. **Change Impact Simulator** – Identify areas that may be affected by a change.
5. **AI First-Contribution Generator** – Find possible beginner-friendly contribution opportunities.
6. **Personalized Adaptive Onboarding** – Generate onboarding guidance based on developer skill level.
7. **AI Developer Mentor** – Ask questions about the actual repository.
8. **Documentation Drift Detector** – Detect possible differences between documentation and source code.
9. **AI Bug Investigation Agent** – Analyze a reported issue and identify relevant evidence.
10. **AI Test Gap & Test Generation Agent** – Identify testing gaps and suggest tests.

## Technology Stack

* Python
* FastAPI
* React
* Vite
* Sentence Transformers
* ChromaDB
* Ollama
* Llama 3.2
* Git
* GitHub
* IBM Bob

## How It Works

```text
GitHub Repository
       ↓
Repository Ingestion
       ↓
Source Code + Documentation + Git History
       ↓
Code Analysis & Knowledge Extraction
       ↓
Semantic Search / Vector Store
       ↓
AI-Assisted Analysis
       ↓
Interactive Developer Onboarding
```

## Large Repository Validation

IntelliOnboard was tested with large open-source repositories, including Kubernetes.

Example Kubernetes analysis:

* **6,712 files indexed**
* **6,413 functions**
* **946 classes**
* **30 commits**

The system also includes bounded processing, caching, timeouts, and error isolation to improve reliability when processing larger repositories.

## IBM Bob

IBM Bob was used throughout development for:

* Feature implementation
* Backend and frontend development
* Debugging
* Testing
* Performance optimization
* Large-repository processing improvements
* Caching and filtering improvements
* Timeout and error-handling improvements

## Vision

IntelliOnboard aims to reduce the time developers spend understanding unfamiliar repositories and help them move from:

**Unfamiliar Codebase → Understanding → Debugging → Testing → First Contribution**

## Live Demo

https://intellionboard-muz32hztj-kakshitha8374-3057.vercel.app/

## Project Structure

```text
intelliboard/
│
├── backend/
│   ├── routers/
│   ├── services/
│   ├── main.py
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   ├── public/
│   └── package.json
│
└── README.md
```

## Project

**IntelliOnboard – AI-Powered Developer Onboarding**

Developed for **IBM Hackathon 2.0**.
