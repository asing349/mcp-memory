from __future__ import annotations

import hashlib
import re
from typing import Iterable


_WS_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[a-z0-9@._-]+")


def normalize_text(t: str) -> str:
    """Lowercase, trim, squash whitespace."""
    return _WS_RE.sub(" ", t.strip().lower())


def sha256_hex(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def tokens(t: str) -> list[str]:
    """Simple alnum tokenizer used by keyword extractor."""
    return _TOKEN_RE.findall(t.lower())


# -------- SimHash (64-bit) for near-duplicate detection) --------
def _hash64(token: str) -> int:
    h = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(h, "big", signed=False)


def simhash64(text: str, ngrams: Iterable[str] | None = None) -> str:
    """
    64-bit SimHash over tokens + bigrams. Returns hex string.
    Deterministic and fast. Not cryptographic.
    """
    if ngrams is None:
        toks = tokens(text)
        bigrams = [f"{a} {b}" for a, b in zip(toks, toks[1:])]
        ngrams = list(toks) + bigrams

    v = [0] * 64
    for g in ngrams:
        hv = _hash64(g)
        for i in range(64):
            if hv & (1 << i):
                v[i] += 1
            else:
                v[i] -= 1
    out = 0
    for i in range(64):
        if v[i] >= 0:
            out |= (1 << i)
    return f"{out:016x}"


def hamming_distance_hex64(a_hex: str, b_hex: str) -> int:
    a = int(a_hex, 16)
    b = int(b_hex, 16)
    return (a ^ b).bit_count()
