
import time
from .config import OPENAI_API_KEY, OPENAI_MODEL

def call_openai(messages, retries=3, backoff=2.0, temperature=0.8):
    """
    Lazy-Import: Verhindert Importfehler, wenn 'openai' nicht installiert ist.
    Nutzt v1 (OpenAI) oder fällt auf v0 (openai.ChatCompletion) zurück.
    """
    last = None
    for i in range(retries):
        try:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=OPENAI_API_KEY)
                resp = client.chat.completions.create(model=OPENAI_MODEL, messages=messages, temperature=temperature)
                return resp.choices[0].message.content
            except Exception as e1:
                # Fallback auf altes SDK
                try:
                    import openai as _openai
                    _openai.api_key = OPENAI_API_KEY
                    resp = _openai.ChatCompletion.create(model=OPENAI_MODEL, messages=messages, temperature=temperature)
                    return resp["choices"][0]["message"]["content"]
                except Exception as e2:
                    raise e2
        except Exception as e:
            last = e
            time.sleep(backoff * (i+1))
    raise RuntimeError(f"OpenAI fehlgeschlagen: {last}")
