"""layer1b/parse/loads_lenient.py — placeholder: llm/client already extracts JSON; truncation-salvage TODO."""
import json
import re


def loads_lenient(txt):
    txt = re.sub(r"<think>.*?</think>", "", txt or "", flags=re.DOTALL)
    m = re.search(r"\{.*\}", txt, re.DOTALL)
    try:
        return json.loads(m.group(0)) if m else {}
    except Exception:
        return {}
