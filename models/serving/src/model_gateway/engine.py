"""The one Ollama chat request shape used by the gateway and by the installer's warm-up.

Ollama reloads a resident model when load options such as the context size change, so the
warm-up must send exactly the options the gateway sends. Standard library only: the installer
runs before the gateway starts.
"""

CONTEXT_TOKENS = 4096


def chat_request(model, prompt, max_tokens):
    return {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "keep_alive": -1,
        "options": {"temperature": 0, "num_predict": max_tokens, "num_ctx": CONTEXT_TOKENS},
    }
