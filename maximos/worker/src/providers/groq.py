import json

from workers import fetch

from providers.prompt import build_prompt

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"


async def analyze(ticker_data: dict, api_key: str) -> str:
    prompt = build_prompt(ticker_data)

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 700,
        "temperature": 0.5,
    }

    response = await fetch(
        GROQ_URL,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        body=json.dumps(payload),
    )

    text = await response.text()
    data = json.loads(text)

    if "error" in data:
        raise RuntimeError(f"Groq error: {data['error'].get('message', data['error'])}")

    return data["choices"][0]["message"]["content"].strip()
