"""Ingest and parse all uploaded brand/audience documents."""
import os
import re
import logging

logger = logging.getLogger(__name__)


def read_all_docs(docs_dir: str, filenames: list[str]) -> dict[str, str]:
    """Read all text documents and return {filename: content}."""
    docs = {}
    for fname in filenames:
        path = os.path.join(docs_dir, fname)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            # Clean up the word-per-line PDF extraction artifacts
            content = _clean_pdf_text(content, fname)
            docs[fname] = content
            logger.info(f"Loaded {fname} ({len(content)} chars)")
        else:
            logger.warning(f"File not found: {path}")
    return docs


def _clean_pdf_text(text: str, filename: str) -> str:
    """Clean up text extracted from PDFs (word-per-line artifacts)."""
    # The Gen Z research doc and research docs are already paragraph-formatted
    if "Gen Z" in filename or "research docs" in filename:
        # These have proper paragraphs, just clean extra whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    # For the other docs (core beliefs, avatar, offer brief), they have
    # word-per-line formatting from PDF extraction. Join words back together.
    lines = text.split('\n')
    cleaned_lines = []
    current_sentence = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_sentence:
                cleaned_lines.append(' '.join(current_sentence))
                current_sentence = []
            cleaned_lines.append('')
            continue
        current_sentence.append(stripped)

    if current_sentence:
        cleaned_lines.append(' '.join(current_sentence))

    return '\n'.join(cleaned_lines).strip()


def extract_keywords(text: str) -> list[str]:
    """Extract significant keywords from text for matching."""
    # Common streetwear/brand keywords to look for
    target_keywords = [
        "heavyweight", "archive", "limited", "drop", "restock", "premium",
        "quality", "exclusive", "underground", "streetwear", "hoodie",
        "oversized", "grail", "NPC", "cringe", "fire", "clean", "hard",
        "authentic", "trust", "transparency", "scarcity", "FOMO",
        "identity", "confidence", "status", "community", "culture",
        "Gen Z", "TikTok", "Instagram", "aesthetic", "fit", "boxy",
        "500gsm", "450gsm", "heavyweight", "embroidery", "stitching",
        "no restock", "one-time", "capsule", "bundle", "stack",
    ]

    text_lower = text.lower()
    found = []
    for kw in target_keywords:
        if kw.lower() in text_lower:
            found.append(kw)
    return list(set(found))
