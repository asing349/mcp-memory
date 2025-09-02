from __future__ import annotations

from collections import Counter
from typing import Iterable

from .utils import tokens


_STOP = {
    "a","an","the","is","are","am","to","of","and","or","for","with","in","on","at","from","by",
    "your","my","our","their","his","her","it","this","that","these","those",
    "be","as","was","were","will","would","can","could","should","do","does","did",
}

def extract_keywords(text: str, max_keywords: int = 8) -> list[str]:
    toks = [t for t in tokens(text) if t not in _STOP]
    bigrams = [f"{a} {b}" for a, b in zip(toks, toks[1:])]
    grams: list[str] = toks + bigrams
    counts = Counter(grams)
    # keep order by frequency then length (prefer informative n-grams)
    top = sorted(counts.items(), key=lambda kv: (kv[1], len(kv[0])), reverse=True)[:max_keywords]
    return [w for w, _ in top]
