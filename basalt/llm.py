
import requests

def call_model(configs, content, prompt, history=None, temperature=0.7, max_tokens=2048):
    """
    Minimal, vanilla-requests wrapper for the big five providers.

    history: list of {"role": "...", "content": "..."} items (optional)
    returns: assistant text (first candidate) or raises RuntimeError
    """

    content = "Text: " + content

    api_key, model, provider = configs["api_key"], configs["model"], configs["provider"]


    if not api_key:
        raise ValueError("api_key is required; missing from configs in call_model ")
    if not model:
        raise ValueError("model is required; missing from configs in call_model ")
    if not provider:
        raise ValueError("provider is required; missing from configs in call_model")


    provider = provider.lower()
    history = history or []


    # ---------- Provider-specific request build ----------
    if provider in ("openai", "mistral", "deepseek"):
        url = {
            "openai":  "https://api.openai.com/v1/chat/completions",
            "mistral": "https://api.mistral.ai/v1/chat/completions",
            "deepseek":"https://api.deepseek.com/v1/chat/completions",
        }[provider]

        headers = {"Authorization": f"Bearer {api_key}",
                   "Content-Type": "application/json"}

        msgs = []
        if prompt:
            msgs.append({"role": "system", "content": prompt})
        msgs.extend(history)
        msgs.append({"role": "user", "content": content})

        body = {
            "model": model,
            "messages": msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        extract = lambda r: r["choices"][0]["message"]["content"]

    elif provider == "anthropic":          # Claude 3
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        msgs = history + [{"role": "user", "content": content}]
        body = {
            "model": model,
            "messages": msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if prompt:
            body["system"] = prompt

        extract = lambda r: r["content"][0]["text"]

    elif provider == "google":             # Gemini 1.5
        url = (f"https://generativelanguage.googleapis.com/v1beta/"
               f"models/{model}:generateContent?key={api_key}")
        headers = {"Content-Type": "application/json"}

        contents = [{"role": m["role"],
                     "parts": [{"text": m["content"]}]} for m in history]
        contents.append({"role": "user", "parts": [{"text": content}]})

        body = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if prompt:
            body["systemInstruction"] = {"parts": [{"text": prompt}]}

        extract = lambda r: r["candidates"][0]["content"]["parts"][0]["text"]

    else:
        raise ValueError(f"Unsupported provider '{provider}'")


    # ---------- Network call ----------
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=30)
        resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"{provider} request failed: {exc}")


    try:
        data = resp.json()
    except ValueError as exc:
        raise RuntimeError(f"{provider} returned non-JSON: {exc}")


    # ---------- Extract assistant text ----------
    try:
        return extract(data)
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"{provider} response format changed: {exc}")
