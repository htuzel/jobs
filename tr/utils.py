"""
Shared utilities for Turkish AI Exposure pipeline.
"""
import re


def slugify_tr(text: str) -> str:
    """Generate a URL-safe slug from Turkish text.

    Maps Turkish-specific characters to ASCII, then collapses
    non-alphanumeric runs to hyphens.

    Implementation note: İ (U+0130) and ı (U+0131) are pre-replaced
    because Python's unicode lower() turns İ into the two-codepoint
    sequence 'i\\u0307' rather than plain 'i', which breaks str.maketrans.
    """
    # Pre-replace multi-codepoint problem chars
    text = text.replace("İ", "i").replace("ı", "i")

    # Single-codepoint Turkish characters safe for str.maketrans
    tr_map = str.maketrans(
        "çğöşüÇĞÖŞÜâîûÂÎÛ",
        "cgosuCGOSUaiuAIU",
    )
    slug = text.lower().translate(tr_map)
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")
