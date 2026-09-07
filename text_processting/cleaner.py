"""Khmer and Multilingual Text Normalization Pipeline for KCMS.

This module provides text cleaning and normalization functions specifically designed
for social media comments (Facebook/TikTok/Telegram) containing Khmer script,
transliterated Khmer (Latin), English, emojis, and informal typing artifacts.

Key transformations:
1. Unicode NFC canonical normalization & HTML unescaping
2. Invisible character & Zero-Width Space (ZWSP) standardization
3. Khmer split-vowel composition (e.g., E + I -> OE 'មើល', E + AA -> OO 'អោ')
4. Deduplication of stacked Khmer diacritics and signs
5. Character, punctuation, and emoji elongation reduction (e.g., យយយយ -> យយ, 😡😡😡 -> 😡😡)
6. URL detection and replacement with [URL] tokens + metadata flagging
7. Whitespace normalization and edge-case filtering
"""

from __future__ import annotations

import html
import re
import unicodedata
from typing import NamedTuple

import pandas as pd


# Regex Patterns
URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
ZWSP_PATTERN = re.compile(r"[\u200b\u200c\u200d\ufeff\u200e\u200f]+")
WHITESPACE_PATTERN = re.compile(r"[\s\u00a0\u3000]+")
REPEATED_CHARS_PATTERN = re.compile(r"(.)\1{2,}")
REPEATED_PUNCT_EXCL = re.compile(r"!{2,}")
REPEATED_PUNCT_QUES = re.compile(r"\?{2,}")
REPEATED_PUNCT_DOTS = re.compile(r"\.{2,}")
REPEATED_KHMER_DIACRITICS = re.compile(r"([\u17B6-\u17D3])\1+")

# Khmer Vowel Composition Mapping (decomposed -> canonical precomposed)
# In informal Khmer typing, compound vowels are frequently typed as separate keystrokes:
KHMER_VOWEL_REPLACEMENTS = [
    ("\u17C1\u17B6", "\u17C4"),  # Sara E + Sara AA -> Sara OO (ស្រៈអោ)
    ("\u17C1\u17B8", "\u17BE"),  # Sara E + Sara I  -> Sara OE (ស្រៈអើ, e.g. មេីល -> មើល)
    ("\u17C1\u17B9", "\u17BF"),  # Sara E + Sara YI -> Sara YA (ស្រៈអឿ)
    ("\u17C1\u17BA", "\u17C0"),  # Sara E + Sara II -> Sara IE (ស្រៈអៀ)
    ("\u17C1\u17BB", "\u17C5"),  # Sara E + Sara U  -> Sara AU (ស្រៈអៅ)
    ("\u17D2{2,}", "\u17D2"),   # Repeated Coeng sign -> single Coeng
    ("\u17D7{2,}", "\u17D7\u17D7"),  # Lekh Too (ៗ) - allow up to 2 for emphasis
]


class CleanResult(NamedTuple):
    text: str
    has_link: bool
    is_valid: bool


def normalize_unicode(text: str) -> str:
    """Unescape HTML entities and normalize to Unicode NFC format."""
    if not isinstance(text, str):
        return ""
    text = html.unescape(text)
    return unicodedata.normalize("NFC", text)


def normalize_khmer_vowels(text: str) -> str:
    """Normalize decomposed Khmer vowel keystrokes into canonical Unicode vowels

    and deduplicate consecutive identical diacritics.
    """
    for decomposed, precomposed in KHMER_VOWEL_REPLACEMENTS:
        text = text.replace(decomposed, precomposed)
    # Deduplicate stacked identical diacritics (e.g. repeated Bantoc, Nikahit, Reahmuk)
    text = REPEATED_KHMER_DIACRITICS.sub(r"\1", text)
    return text


def clean_invisible_chars(text: str) -> str:
    """Normalize zero-width spaces (ZWSP), joiners, and BOM markers to standard spaces."""
    return ZWSP_PATTERN.sub(" ", text)


def normalize_elongation(text: str, max_repeat: int = 2) -> str:
    """Reduce prolonged character repetitions (e.g., 'heee' -> 'hee', 'ស្រលាញ់ណាស់សស' -> '...សស').

    Preserves emphasis signal while preventing token explosion in the transformer vocabulary.
    """
    # Cap 3+ identical consecutive characters to max_repeat
    text = REPEATED_CHARS_PATTERN.sub(r"\1" * max_repeat, text)
    # Standardize punctuation repetitions
    text = REPEATED_PUNCT_EXCL.sub("!", text)
    text = REPEATED_PUNCT_QUES.sub("?", text)
    text = REPEATED_PUNCT_DOTS.sub("...", text)
    return text


def clean_urls(text: str, replacement: str = "[URL]") -> tuple[str, bool]:
    """Detect URLs, replace them with a standardized token, and report link presence."""
    has_link = bool(URL_PATTERN.search(text))
    cleaned_text = URL_PATTERN.sub(f" {replacement} ", text)
    return cleaned_text, has_link


def normalize_whitespace(text: str) -> str:
    """Collapse consecutive spaces, tabs, and newlines into a single space and strip borders."""
    return WHITESPACE_PATTERN.sub(" ", text).strip()


def normalize_comment(
    text: str,
    url_replacement: str = "[URL]",
    max_repeat: int = 2,
    min_length: int = 2,
) -> CleanResult:
    """Run full text normalization on a single comment.

    Returns:
        CleanResult(text=normalized_text, has_link=bool, is_valid=bool)
    """
    if not isinstance(text, str):
        return CleanResult(text="", has_link=False, is_valid=False)

    # 1. Unicode & HTML
    t = normalize_unicode(text)

    # 2. Invisible chars / ZWSP
    t = clean_invisible_chars(t)

    # 3. Khmer vowel composition & diacritic deduplication
    t = normalize_khmer_vowels(t)

    # 4. URLs
    t, has_link = clean_urls(t, replacement=url_replacement)

    # 5. Elongation reduction
    t = normalize_elongation(t, max_repeat=max_repeat)

    # 6. Whitespace normalization
    t = normalize_whitespace(t)

    # 7. Validity check (reject empty or single-character comments, or standalone URL tokens with no context)
    is_standalone_url = (t == url_replacement)
    is_valid = len(t) >= min_length and not is_standalone_url

    return CleanResult(text=t, has_link=has_link, is_valid=is_valid)


def clean_dataframe(
    df: pd.DataFrame,
    text_column: str = "text",
    drop_invalid: bool = True,
    drop_duplicates: bool = True,
) -> pd.DataFrame:
    """Normalize text across a dataframe, flag links, drop duplicates,

    and ensure compliance with KCMS AI engine schema.
    """
    out_df = df.copy()

    # Apply normalization
    results = [normalize_comment(t) for t in out_df[text_column]]
    out_df["text"] = [r.text for r in results]
    out_df["link_flagged"] = [r.has_link for r in results]
    out_df["is_valid"] = [r.is_valid for r in results]

    # Filter invalid
    if drop_invalid:
        out_df = out_df[out_df["is_valid"]].drop(columns=["is_valid"])
    else:
        out_df = out_df.drop(columns=["is_valid"])

    # Deduplicate based on normalized text
    if drop_duplicates:
        out_df = out_df.drop_duplicates(subset=["text"]).reset_index(drop=True)

    # Ensure required AI Engine columns exist
    defaults = {
        "severity_id": 0,
        "target_id": 0,
        "has_pii": False,
        "link_flagged": False,
        "annotator": "",
        "split": "train",
        "notes": "",
    }
    for col, default_val in defaults.items():
        if col not in out_df.columns:
            out_df[col] = default_val
        else:
            out_df[col] = out_df[col].fillna(default_val)

    return out_df
