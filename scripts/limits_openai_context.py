import os, asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Load .env from the current working dir (repo root)
load_dotenv()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

async def try_len(client, chars: int):
    blob = ("function x(){return 1}\\n" * max(1, chars // 20))[:chars]
    try:
        r = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": f"Summarize:\\n```js\\n{blob}\\n```"}],
            temperature=0.0,
        )
        _ = r.choices[0].message.content
        return chars, "ok"
    except Exception as e:
        msg = str(e).lower()
        if "context" in msg or "max context" in msg or "400" in msg:
            return chars, "context_limit"
        return chars, ("error:" + msg[:200])

async def main():
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set (ensure .env is present and load_dotenv() ran)")

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    lo, hi, step = 10_000, 400_000, 5_000
    last_ok = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        size, res = await try_len(client, mid)
        print(f"{size}\t{res}")
        if res == "ok":
            last_ok = size
            lo = mid + step
        else:
            hi = mid - step
    print(f"max_ok_chars={last_ok}")

if __name__ == "__main__":
    asyncio.run(main())
