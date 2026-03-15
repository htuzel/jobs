"""
Shared utilities for Turkish AI Exposure pipeline.
"""
import re


def slugify_tr(text: str) -> str:
    """Generate URL-safe slug from Turkish text.
    Handles all Turkish special characters including circumflexed vowels.
    """
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜâîûÂÎÛ", "cgiosuCGIOSUaiuAIU")
    slug = text.lower().translate(tr_map)
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")
