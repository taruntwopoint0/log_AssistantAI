"""Diagnose the Gemini key and model. Run: python check_ai.py

engine/writer.py swallows every exception on purpose - a model failure must
never take the tool down. The cost of that is a bad key looks exactly like no
key at all: you just get template summaries and no error. This script is the
escape hatch. It makes the same call with the error surfaced.

Never prints the key itself.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from main import _load_dotenv  # also loads backend/.env

_load_dotenv()

KEY = os.environ.get("GEMINI_API_KEY", "").strip()
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")


def mask(k: str) -> str:
    return f"{k[:4]}...{k[-4:]} ({len(k)} chars)" if len(k) > 12 else "(too short)"


def main() -> int:
    print(f"env file      : {Path(__file__).resolve().parent / '.env'}")
    print(f"key present   : {bool(KEY)}")
    if not KEY:
        print()
        print("No GEMINI_API_KEY found.")
        print("  1. Get a key at https://aistudio.google.com/apikey")
        print("  2. copy .env.example to .env and paste the key in")
        print("  3. re-run this script")
        return 1

    print(f"key           : {mask(KEY)}")
    print(f"model         : {MODEL}")

    if KEY == "paste-your-key-here":
        print("\nThat is still the placeholder from .env.example, not a real key.")
        return 1

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("\ngoogle-genai is not installed. Run: pip install google-genai")
        return 1

    print("\ncalling the API...")
    try:
        client = genai.Client(api_key=KEY)
        resp = client.models.generate_content(
            model=MODEL,
            contents="Reply with exactly: ok",
            config=types.GenerateContentConfig(temperature=0, max_output_tokens=2000),
        )
    except Exception as exc:  # surfaced deliberately, unlike in writer.py
        print(f"\nFAILED: {type(exc).__name__}")
        print(f"  {exc}")
        print()
        text = str(exc).lower()
        if "api key not valid" in text or "api_key_invalid" in text:
            print("  The key is wrong or was revoked. Create a fresh one in AI Studio.")
        elif "not found" in text or "404" in text:
            print(f"  The model id {MODEL!r} was rejected. Check the current list at")
            print("  https://ai.google.dev/gemini-api/docs/models and set GEMINI_MODEL.")
        elif "quota" in text or "429" in text or "resource_exhausted" in text:
            print("  Rate limited or out of free-tier quota. Wait, or enable billing.")
        elif "permission" in text or "403" in text:
            print("  The key exists but lacks access. Check the Cloud project the key")
            print("  belongs to has the Generative Language API enabled.")
        return 1

    print(f"OK. Model replied: {(resp.text or '').strip()[:80]!r}")
    print("\nThe dashboard will now show 'written by model' instead of")
    print("'template, no model' under the summary paragraph.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
