"""Name normalization and conservative phrase matching. Python 3.9 compatible."""
from __future__ import annotations

import re
from typing import Iterable, List, Optional, Tuple

# Trailing tokens stripped only when doing a "core" comparison, so a seed
# like "warfarin" can match a label generic name "WARFARIN SODIUM".
DOSE_FORM_TOKENS = frozenset(
    {
        "tablet",
        "tablets",
        "capsule",
        "capsules",
        "injection",
        "injectable",
        "solution",
        "suspension",
        "cream",
        "ointment",
        "gel",
        "lotion",
        "syrup",
        "elixir",
        "spray",
        "inhalation",
        "inhaler",
        "oral",
        "topical",
        "extended",
        "release",
        "delayed",
        "immediate",
        "disintegrating",
        "chewable",
        "film",
        "coated",
        "for",
        "use",
        "usp",
        "kit",
        "powder",
        "concentrate",
        "prefilled",
        "syringe",
        "vial",
        "iv",
        "im",
        "subcutaneous",
        "intravenous",
        "intramuscular",
    }
)

SALT_TOKENS = frozenset(
    {
        "sodium",
        "potassium",
        "calcium",
        "magnesium",
        "hydrochloride",
        "hydrobromide",
        "sulfate",
        "sulphate",
        "phosphate",
        "acetate",
        "maleate",
        "succinate",
        "tartrate",
        "citrate",
        "mesylate",
        "besylate",
        "fumarate",
        "bitartrate",
        "chloride",
        "bromide",
        "iodide",
        "carbonate",
        "bicarbonate",
        "monohydrate",
        "dihydrate",
        "trihydrate",
        "anhydrous",
        "free",
        "base",
        "lysine",
        "arginine",
        "etexilate",  # dabigatran etexilate vs dabigatran etexilate mesylate
        "tosylate",
        "tromethamine",
        "medoxomil",
        "propionate",
        "valerate",
        "acetonide",
        "hexacetonide",
        "enanthate",
        "cypionate",
        "pivalate",
        "butyrate",
        "complex",
    }
)

# Bare tokens that are too common to use as interaction/ingredient aliases.
STOP_ALIASES = frozenset(
    {
        "sodium",
        "potassium",
        "calcium",
        "magnesium",
        "chloride",
        "hydrochloride",
        "water",
        "starch",
        "lactose",
        "alcohol",
        "acid",
        "base",
        "free",
        "anhydrous",
        "monohydrate",
        "injection",
        "tablet",
        "tablets",
        "oral",
        "human",
        "iron",  # too easy to match "iron deficiency"
        "zinc",
        "gold",
        "urea",
        "oil",
        "and",
        "for",
        "use",
        "usp",
    }
)

# Four-letter tokens that should never be treated as a biosimilar suffix.
NOT_BIOSIMILAR_SUFFIXES = frozenset(
    {
        "acid",
        "oral",
        "plus",
        "forte",
        "free",
        "base",
        "pred",
        "comp",
        "zinc",
        "iron",
        "gold",
        "alpha",
        "beta",
        "alfa",
    }
)

_HYPHEN_SUFFIX = re.compile(r"-([A-Za-z]{4})\s*$")


def strip_comment(line: str) -> str:
    return line.split("#", 1)[0].strip()


def load_name_list(path) -> List[str]:
    names: List[str] = []
    seen = set()
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            name = strip_comment(raw)
            if not name:
                continue
            key = normalize_name(name)
            if not key or key in seen:
                continue
            seen.add(key)
            names.append(name)
    return names


def strip_biosimilar_hyphen_suffix(name: str) -> str:
    """Remove a trailing -xxxx biosimilar suffix when present, e.g. alfa-epbx."""
    match = _HYPHEN_SUFFIX.search(name.strip())
    if not match:
        return name
    suffix = match.group(1).lower()
    if suffix in NOT_BIOSIMILAR_SUFFIXES:
        return name
    return name[: match.start()]


def normalize_name(name: str) -> str:
    text = strip_biosimilar_hyphen_suffix(name).strip().lower()
    text = text.replace("\u2019", "'")
    text = text.replace("'", "")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def core_name(name: str) -> str:
    """Lowercase name with trailing salt/dose-form tokens removed when safe."""
    tokens = normalize_name(name).split()
    if not tokens:
        return ""
    # Combination products: only strip trailing dose-form words, keep "and X".
    if "and" in tokens:
        while tokens and tokens[-1] in DOSE_FORM_TOKENS:
            tokens.pop()
        return " ".join(tokens)
    while tokens:
        last = tokens[-1]
        if last in DOSE_FORM_TOKENS:
            tokens.pop()
            continue
        if last in SALT_TOKENS and len(tokens) > 1:
            tokens.pop()
            continue
        break
    return " ".join(tokens)


def generic_matches_seed(generic_name: str, seed: str) -> bool:
    core_generic = core_name(generic_name)
    core_seed = core_name(seed)
    if core_generic and core_seed and core_generic == core_seed:
        return True
    return normalize_name(generic_name) == normalize_name(seed)


def alias_is_usable(name: str, min_chars: int = 5) -> bool:
    norm = normalize_name(name)
    if len(norm) < min_chars:
        return False
    if norm in STOP_ALIASES:
        return False
    tokens = norm.split()
    if len(tokens) == 1 and tokens[0] in STOP_ALIASES:
        return False
    return True


def name_pattern(name: str) -> Optional[re.Pattern]:
    tokens = normalize_name(name).split()
    if not tokens:
        return None
    body = r"\s+".join(re.escape(token) for token in tokens)
    return re.compile(r"\b" + body + r"\b", re.IGNORECASE)


def find_mentions(text: str, name: str) -> List[Tuple[int, int]]:
    """Return start/end spans of word-boundary matches in text."""
    pattern = name_pattern(name)
    if pattern is None or not text:
        return []
    return [(m.start(), m.end()) for m in pattern.finditer(text)]


def clip_text(text: Optional[str], length: int = 400) -> Optional[str]:
    """Trim to length, snapping the cut to a word boundary, with an ellipsis."""
    if not text:
        return text
    compact = " ".join(text.split())
    if len(compact) <= length:
        return compact
    budget = length - 3
    if budget < 1:
        return "..."
    cut = compact[:budget].rstrip()
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0].rstrip()
    if not cut:
        cut = compact[:budget].rstrip()
    return cut + "..."


def snippet_around(text: str, start: int, end: int, radius: int = 140) -> str:
    """Return a window around [start, end), snapped to word boundaries, with ellipses."""
    if not text:
        return ""
    lo = max(0, start - radius)
    hi = min(len(text), end + radius)
    if lo > 0:
        while lo < start and lo < len(text) and not text[lo].isspace():
            lo += 1
        while lo < start and lo < len(text) and text[lo].isspace():
            lo += 1
    if hi < len(text):
        while hi > end and hi > 0 and not text[hi - 1].isspace():
            hi -= 1
        while hi > end and hi > 0 and text[hi - 1].isspace():
            hi -= 1
    chunk = re.sub(r"\s+", " ", text[lo:hi]).strip()
    if lo > 0:
        chunk = "..." + chunk
    if hi < len(text):
        chunk = chunk + "..."
    return chunk


def first_mention_snippet(text: str, name: str, radius: int = 140) -> Optional[str]:
    spans = find_mentions(text, name)
    if not spans:
        return None
    start, end = spans[0]
    return snippet_around(text, start, end, radius=radius)


def join_field(value) -> str:
    """Join an openFDA list-or-string field into one text block."""
    if value is None:
        return ""
    if isinstance(value, list):
        parts = [part.strip() for part in value if isinstance(part, str) and part.strip()]
        return "\n".join(parts)
    if isinstance(value, str):
        return value.strip()
    return str(value)


def unique_strings(values: Iterable[object]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in values:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not text:
            continue
        key = normalize_name(text) or text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def nonoverlapping_phrase_hits(text: str, phrases: Iterable[str], radius: int = 140) -> List[Tuple[str, str]]:
    """Return (phrase, snippet) for word-boundary hits, longest non-overlapping first."""
    scored = []
    for phrase in phrases:
        spans = find_mentions(text, phrase)
        if not spans:
            continue
        start, end = spans[0]
        scored.append((-(end - start), start, end, phrase, snippet_around(text, start, end, radius=radius)))
    scored.sort()
    used = []
    hits = []
    for _neg, start, end, phrase, snippet in scored:
        if any(not (end <= lo or start >= hi) for lo, hi in used):
            continue
        used.append((start, end))
        hits.append((phrase, snippet))
    return hits
