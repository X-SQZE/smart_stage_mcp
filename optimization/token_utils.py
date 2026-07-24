"""Estimation du nombre de tokens d'un texte.

Utilise `tiktoken` si le paquet est disponible (approximation raisonnable
même pour des modèles non-OpenAI comme Gemini), sinon retombe sur une
heuristique simple (~4 caractères par token).
"""
from __future__ import annotations

try:
    import tiktoken

    _ENCODING = tiktoken.get_encoding("cl100k_base")
except Exception:  # pragma: no cover - tiktoken absent ou erreur d'init
    _ENCODING = None


def estimate_tokens(text: str) -> int:
    """Estime le nombre de tokens d'un texte. Ne lève jamais d'exception."""
    if not text:
        return 0
    if _ENCODING is not None:
        try:
            return len(_ENCODING.encode(text))
        except Exception:
            pass
    return max(1, len(text) // 4)
