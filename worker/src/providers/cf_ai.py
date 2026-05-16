from providers.prompt import build_prompt

MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"


async def analyze(ticker_data: dict, ai_binding) -> str:
    prompt = build_prompt(ticker_data)
    result = await ai_binding.run(
        MODEL,
        {"messages": [{"role": "user", "content": prompt}]},
    )
    return result["response"].strip()
