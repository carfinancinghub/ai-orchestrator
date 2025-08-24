import os, importlib, sys

def check(sdk_name, import_name, env_keys):
    print(f"\n== {sdk_name} ==")
    env_ok = all(os.getenv(k) for k in env_keys)
    print(f"env: {'ok' if env_ok else 'missing'} ({', '.join(env_keys)})")
    try:
        importlib.import_module(import_name)
        print("import: ok")
    except Exception as e:
        print(f"import: missing ({e.__class__.__name__}: {e})")

if __name__ == "__main__":
    print("LLM smoketest (imports only; does not call APIs)\nPython:", sys.version)
    check("OpenAI",      "openai",                 ["OPENAI_API_KEY"])
    check("Anthropic",   "anthropic",              ["ANTHROPIC_API_KEY"])
    check("Google GenAI","google.generativeai",    ["GOOGLE_API_KEY"])
    print("\nDone.")
