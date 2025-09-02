from __future__ import annotations

import re
from typing import Sequence

# Rule-based categories. You can expand later.
_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("technical", re.compile(r"\b(github|repo|api|sdk|server|endpoint|docker|node|react|typescript|python)\b")),
    ("contacts",  re.compile(r"\b(email|phone|contact|linkedin|@)\b")),
    ("finance",   re.compile(r"\b(bank|invoice|payment|usd|\$|card|account number)\b")),
    ("work",      re.compile(r"\b(meeting|deadline|jira|ticket|client|deliverable|sprint)\b")),
]

def categorize(text: str, keywords: Sequence[str]) -> str:
    blob = f"{text.lower()} {' '.join(keywords).lower()}"
    for name, rx in _RULES:
        if rx.search(blob):
            return name
    return "personal"
