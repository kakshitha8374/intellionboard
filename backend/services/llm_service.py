"""
llm_service.py — Optimized Ollama integration with:
  - Context truncation to prevent huge prompts
  - Reduced max_tokens / output length limit
  - Focused retrieval (only relevant chunks sent)
  - Proper timeout handling
  - Useful error messages on failure
"""

import requests


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2:3b"

# Context limits to keep prompts small and generation fast
MAX_CONTEXT_CHARS = 6000    # Maximum characters of repository context per prompt
MAX_HISTORY_CHARS = 1200    # Maximum characters of git history in prompt
MAX_RESPONSE_TOKENS = 600   # Limit output length for faster responses
LLM_TIMEOUT_SECONDS = 180   # Maximum wait for Ollama response


def _truncate(text: str, max_chars: int, label: str = "context") -> str:
    """Truncate text with a clear truncation notice."""
    if len(text) <= max_chars:
        return text
    cutoff = max_chars - 80
    return text[:cutoff] + f"\n\n[...{label} truncated at {max_chars} chars for performance...]"


def generate_answer(question: str, context: str) -> str:
    """
    Generate an answer using Ollama and the retrieved repository context.

    Context is truncated to MAX_CONTEXT_CHARS to keep prompts fast.
    """
    # Truncate context to keep the prompt manageable
    truncated_context = _truncate(context, MAX_CONTEXT_CHARS, "repository context")

    prompt = f"""You are IntelliOnboard, an AI assistant that helps developers understand GitHub repositories.

Answer the question using ONLY the repository context provided below.
If the context lacks enough information, say: "I don't have enough information in the repository context."
Be concise and direct. Do not invent code, files, or features.

Repository Context:
{truncated_context}

Question: {question}

Answer:"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": MAX_RESPONSE_TOKENS,
                    "temperature": 0.1,
                    "top_p": 0.9,
                },
            },
            timeout=LLM_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()

    except requests.exceptions.ConnectionError:
        return (
            "Ollama is not running. Please start Ollama with: ollama serve\n"
            "Then ensure the model is available: ollama pull llama3.2:3b"
        )
    except requests.exceptions.Timeout:
        return (
            f"The AI response timed out after {LLM_TIMEOUT_SECONDS}s. "
            "The model may be busy. Please try again."
        )
    except requests.exceptions.HTTPError as exc:
        return f"Ollama API error: {exc}"
    except Exception as exc:
        return f"AI generation failed: {exc}"
