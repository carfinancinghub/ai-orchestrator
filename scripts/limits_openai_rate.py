import os, asyncio, time
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
N = int(os.getenv("OAI_RATE_N", "20"))
CONC = int(os.getenv("OAI_RATE_CONC", "5"))

def redact(s: str) -> str:
    if not s: return s
    s = s.replace("sk-", "sk-[REDACTED]").replace("Bearer ", "Bearer [REDACTED]")
    return s

async def one(client, i):
    t0 = time.time()
    try:
        r = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": f"ping {i}"}],
            temperature=0.0,
        )
        dt = int((time.time() - t0) * 1000)
        return {"i": i, "ok": True, "ms": dt}
    except Exception as e:
        return {"i": i, "ok": False, "err": redact(str(e))[:180]}

async def main():
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set (ensure .env is present and load_dotenv() ran)")

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    sem = asyncio.Semaphore(CONC)
    async def run(i):
        async with sem:
            return await one(client, i)

    tasks = [asyncio.create_task(run(i)) for i in range(N)]
    out = await asyncio.gather(*tasks)
    oks = sum(1 for x in out if x["ok"])
    fails = [x for x in out if not x["ok"]]
    print({"sent": N, "ok": oks, "fail": len(fails), "fails": fails[:5]})

if __name__ == "__main__":
    asyncio.run(main())
