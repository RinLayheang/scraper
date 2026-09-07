"""Khmer and Multilingual Text Normalization Pipeline for KCMS.

This module provides text cleaning and normalization functions specifically designed
for social media comments (Facebook/TikTok/Telegram) containing Khmer script,
transliterated Khmer (Latin), English, and informal typing artifacts.

Key transformations:
1. Unicode NFC canonical normalization & HTML unescaping
2. Invisible character & Zero-Width Space (ZWSP) standardization
3. Khmer split-vowel composition (e.g., E + I -> OE 'មើល', E + AA -> OO 'អោ')
4. Deduplication of stacked Khmer diacritics and signs
5. Character & punctuation elongation reduction (e.g., យយយយ -> យយ, heee -> hee)
6. URL detection and replacement with [URL] tokens + metadata flagging
7. Emoji removal (stripping pictographs, emoticons, symbols)
8. Stop word removal (Khmer contextual boundary-safe & English stopwords, preserving negations)
9. Whitespace normalization and edge-case filtering
"""

from __future__ import annotations

import html
import re
import unicodedata
from typing import NamedTuple

import pandas as pd

# ---------------------------------------------------------------------------
# Regex Patterns
# ---------------------------------------------------------------------------
URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
ZWSP_PATTERN = re.compile(r"[\u200b\u200c\u200d\ufeff\u200e\u200f]+")
WHITESPACE_PATTERN = re.compile(r"[\s\u00a0\u3000]+")
REPEATED_CHARS_PATTERN = re.compile(r"(.)\1{2,}")
REPEATED_PUNCT_EXCL = re.compile(r"!{2,}")
REPEATED_PUNCT_QUES = re.compile(r"\?{2,}")
REPEATED_PUNCT_DOTS = re.compile(r"\.{2,}")
REPEATED_KHMER_DIACRITICS = re.compile(r"([\u17B6-\u17D3])\1+")

# Comprehensive Emoji Regex covering Emoticons, Pictographs, Dingbats, Flags & Modifiers
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U0001F900-\U0001F9FF"  # supplemental symbols and pictographs
    "\U0001FA00-\U0001FA6F"  # chess symbols
    "\U0001FA70-\U0001FAFF"  # symbols and pictographs extended-A
    "\U00002702-\U000027B0"  # dingbats
    "\U000024C2-\U0001F251"  # enclosed characters
    "\u2600-\u26FF"          # misc symbols (e.g. ☀️, ❤️)
    "\u2700-\u27BF"          # dingbats
    "\uFE00-\uFE0F"          # variation selectors
    "\u200D"                 # zero width joiner (in emoji sequences)
    "]+",
    flags=re.UNICODE,
)

# ---------------------------------------------------------------------------
# Khmer Vowel Composition Mapping (decomposed -> canonical precomposed)
# ---------------------------------------------------------------------------
KHMER_VOWEL_REPLACEMENTS = [
    ("\u17C1\u17B6", "\u17C4"),  # Sara E + Sara AA -> Sara OO (ស្រៈអោ)
    ("\u17C1\u17B8", "\u17BE"),  # Sara E + Sara I  -> Sara OE (ស្រៈអើ, e.g. មេីល -> មើល)
    ("\u17C1\u17B9", "\u17BF"),  # Sara E + Sara YI -> Sara YA (ស្រៈអឿ)
    ("\u17C1\u17BA", "\u17C0"),  # Sara E + Sara II -> Sara IE (ស្រៈអៀ)
    ("\u17C1\u17BB", "\u17C5"),  # Sara E + Sara U  -> Sara AU (ស្រៈអៅ)
    ("\u17D2{2,}", "\u17D2"),   # Repeated Coeng sign -> single Coeng
    ("\u17D7{2,}", "\u17D7\u17D7"),  # Lekh Too (ៗ) - allow up to 2 for emphasis
]

# ---------------------------------------------------------------------------
# Stop Words Definitions
# ---------------------------------------------------------------------------
# Curated Khmer grammatical particles, prepositions, conjunctions, and copulas.
# NOTE: Negative particles (មិន, កុំ, ពុំ, មិនមែន) are excluded to preserve sentiment and moderation integrity.
KHMER_STOPWORDS = {
    # Conjunctions & prepositions
    "និង", "ឬ", "ឬក៏", "ដែល", "នៃ", "ក្នុង", "លើ", "ក្រោម", "ពី", "ដល់",
    "ចំពោះ", "ដោយ", "ដើម្បី", "ព្រោះ", "ដោយសារ", "ប៉ុន្តែ", "តែ", "បើ",
    "ប្រសិន", "ប្រសិនបើ", "ទោះបី", "ទោះជា", "ដូចជា", "តាម", "អំពី", "សម្រាប់",
    # Copulas, aspect & tense markers
    "គឺ", "គឺថា", "ជា", "បាន", "នៅ", "កំពុង", "នឹង", "អាច",
    # Demonstratives & quantifiers
    "នេះ", "នោះ", "ឯណោះ", "ឯនេះ", "ទាំងនេះ", "ទាំងនោះ", "មួយ", "ខ្លះ", "ផ្សេង", "ទាំងអស់",
    # Conversational & final particles
    "ហ្នឹង", "ណា", "ណ៎ា", "អេីយ", "អើយ",
}

# Standard English stop words (negations like no/not/nor/never are preserved)
try:
    from nltk.corpus import stopwords
    _nltk_en = set(stopwords.words("english"))
except Exception:
    _nltk_en = {
        "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your",
        "yours", "yourself", "yourselves", "he", "him", "his", "himself", "she",
        "her", "hers", "herself", "it", "its", "itself", "they", "them", "their",
        "theirs", "themselves", "what", "which", "who", "whom", "this", "that",
        "these", "those", "am", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "having", "do", "does", "did", "doing", "a", "an",
        "the", "and", "but", "if", "or", "because", "as", "until", "while", "of",
        "at", "by", "for", "with", "about", "against", "between", "into", "through",
        "during", "before", "after", "above", "below", "to", "from", "up", "down",
        "in", "out", "on", "off", "over", "under", "again", "further", "then", "once",
        "here", "there", "when", "where", "why", "how", "all", "any", "both", "each",
        "few", "more", "most", "other", "some", "such", "only", "own", "same", "so",
        "than", "too", "very", "s", "t", "can", "will", "just", "don", "should", "now"
    }

ENGLISH_STOPWORDS = _nltk_en - {"no", "not", "nor", "neither", "never"}

# Boundary-safe regex for Khmer stop words:
# Prevents stripping substrings from compound words (e.g. preserves 'ជា' in 'កម្ពុជា')
_sorted_khmer_stops = sorted(KHMER_STOPWORDS, key=len, reverse=True)
KHMER_STOP_REGEX = re.compile(
    r"(?<![\u1780-\u17D3])(" + "|".join(re.escape(w) for w in _sorted_khmer_stops) + r")(?![\u1780-\u17D3])"
)

ENGLISH_STOP_REGEX = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in ENGLISH_STOPWORDS) + r")\b",
    re.IGNORECASE,
)


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


def remove_emojis(text: str) -> str:
    """Remove emojis, emoticons, pictographs, and dingbats from text."""
    return EMOJI_PATTERN.sub("", text)


def remove_stopwords(
    text: str,
    remove_khmer: bool = True,
    remove_english: bool = True,
) -> str:
    """Remove Khmer and English stop words with boundary safety (preserving negations)."""
    t = text
    if remove_khmer:
        t = KHMER_STOP_REGEX.sub(" ", t)
    if remove_english:
        t = ENGLISH_STOP_REGEX.sub(" ", t)
    return t


def normalize_whitespace(text: str) -> str:
    """Collapse consecutive spaces, tabs, and newlines into a single space and strip borders."""
    return WHITESPACE_PATTERN.sub(" ", text).strip()


def normalize_comment(
    text: str,
    url_replacement: str = "[URL]",
    max_repeat: int = 2,
    remove_emoji: bool = True,
    remove_stop_words: bool = True,
    min_length: int = 2,
) -> CleanResult:
    """Run full text normalization on a single comment.

    Args:
        text: Raw input text.
        url_replacement: Replacement token for URLs (default '[URL]').
        max_repeat: Maximum consecutive repeated characters allowed (default 2).
        remove_emoji: If True, strip all emojis (default True).
        remove_stop_words: If True, remove Khmer and English stop words (default True).
        min_length: Minimum character length for valid comments (default 2).

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

    # 5. Emoji removal (if enabled)
    if remove_emoji:
        t = remove_emojis(t)

    # 6. Stop word removal (if enabled)
    if remove_stop_words:
        t = remove_stopwords(t)

    # 7. Elongation reduction
    t = normalize_elongation(t, max_repeat=max_repeat)

    # 8. Whitespace normalization
    t = normalize_whitespace(t)

    # 9. Validity check (reject empty or single-character comments, or standalone URL tokens with no context)
    is_standalone_url = (t == url_replacement)
    is_valid = len(t) >= min_length and not is_standalone_url

    return CleanResult(text=t, has_link=has_link, is_valid=is_valid)


def clean_dataframe(
    df: pd.DataFrame,
    text_column: str = "text",
    remove_emoji: bool = True,
    remove_stop_words: bool = True,
    drop_invalid: bool = True,
    drop_duplicates: bool = True,
) -> pd.DataFrame:
    """Normalize text across a dataframe, flag links, drop duplicates,

    and ensure compliance with KCMS AI engine schema.
    """
    out_df = df.copy()

    # Apply normalization
    results = [
        normalize_comment(
            t,
            remove_emoji=remove_emoji,
            remove_stop_words=remove_stop_words,
        )
        for t in out_df[text_column]
    ]
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
