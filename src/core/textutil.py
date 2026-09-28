"""Deterministic text helpers shared by extraction, validation and diffing.
Plain Python, no models."""
import re

NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "twenty": 20, "twenty-four": 24,
    "thirty": 30, "forty-five": 45, "sixty": 60, "ninety": 90, "hundred": 100,
}

UNIT_HOURS = {
    "minute": 1 / 60, "minutes": 1 / 60,
    "hour": 1, "hours": 1,
    "day": 24, "days": 24,
    "working day": 24, "working days": 24,
    "calendar day": 24, "calendar days": 24,
    "business day": 24, "business days": 24,
    "week": 168, "weeks": 168, "fortnight": 336,
    "month": 720, "months": 720,
}

_NUM = r"(\d+|" + "|".join(sorted((re.escape(w) for w in NUMBER_WORDS), key=len, reverse=True)) + r")"
DURATION_RE = re.compile(
    rf"\b{_NUM}[\s-]+(?:full\s+)?((?:calendar|working|business)\s+days?|minutes?|hours?|days?|weeks?|months?)\b",
    re.IGNORECASE,
)
FORTNIGHT_RE = re.compile(r"\b(a|one) fortnight\b", re.IGNORECASE)
EVERY_UNIT_RE = re.compile(r"\b(every|each)\s+(day|week|month|fortnight)\b", re.IGNORECASE)
COUNT_RE = re.compile(
    rf"\b(?:at least|minimum of|up to|maximum of|more than|exceed|exceeds)\s+{_NUM}\s+([a-z]+)", re.IGNORECASE
)
PERCENT_RE = re.compile(r"\b(\d+(?:\.\d+)?|" + "|".join(NUMBER_WORDS) + r")\s*(%|percent)", re.IGNORECASE)
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\"'])")
SECTION_PREFIX = re.compile(r"^\s*\d{1,2}(?:\.\d{1,2}){0,3}\.?\s+")
WORD_RE = re.compile(r"[a-z0-9]+(?:['-][a-z0-9]+)*")

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "by", "with", "at", "from",
    "is", "are", "be", "been", "was", "were", "it", "its", "this", "that", "these", "those",
    "as", "any", "all", "their", "they", "your", "you", "our", "we", "not", "no", "must",
    "shall", "should", "may", "can", "will", "has", "have", "had", "do", "does", "into",
    "than", "which", "who", "what", "when", "where", "each", "every", "only", "also",
}


def to_number(token: str) -> float | None:
    token = token.lower()
    if token.replace(".", "", 1).isdigit():
        return float(token)
    return NUMBER_WORDS.get(token)


def durations(text: str) -> list[dict]:
    """Every duration phrase in the text, normalised to hours."""
    found = []
    # "within an hour" is a deadline; "on a working day" is not.
    text = re.sub(r"\b(within|in|after|every) (a|an) ", r"\1 one ", text, flags=re.IGNORECASE)
    for match in DURATION_RE.finditer(text):
        value = to_number(match.group(1))
        unit = re.sub(r"\s+", " ", match.group(2).lower())
        if value is None:
            continue
        hours = value * UNIT_HOURS.get(unit, UNIT_HOURS.get(unit.split()[-1], 24))
        found.append({"text": match.group(0), "value": value, "unit": unit, "hours": hours})
    for match in FORTNIGHT_RE.finditer(text):
        found.append({"text": match.group(0), "value": 2, "unit": "weeks", "hours": 336})
    # "every week" / "each month" is a frequency of one unit.
    for match in EVERY_UNIT_RE.finditer(text):
        unit = match.group(2).lower()
        found.append({"text": match.group(0), "value": 1, "unit": unit, "hours": UNIT_HOURS[unit]})
    return found


def numeric_facts(text: str) -> list[dict]:
    """Durations, counts ("at least fourteen characters") and percentages."""
    facts = [{"kind": "duration", **d} for d in durations(text)]
    for match in COUNT_RE.finditer(text):
        value = to_number(match.group(1))
        if value is not None:
            facts.append({"kind": "count", "text": match.group(0), "value": value,
                          "unit": match.group(2).lower()})
    for match in PERCENT_RE.finditer(text):
        value = to_number(match.group(1))
        if value is not None:
            facts.append({"kind": "percent", "text": match.group(0), "value": value, "unit": "%"})
    return facts


def deadline_days(text: str) -> int | None:
    """The tightest deadline in a sentence, in whole days (hours round up to 1)."""
    hours = [d["hours"] for d in durations(text)]
    if not hours:
        return None
    tightest = min(hours)
    return max(1, round(tightest / 24)) if tightest >= 24 else 1


def split_sentences(text: str) -> list[str]:
    text = SECTION_PREFIX.sub("", text.strip())
    parts = [p.strip() for p in SENTENCE_SPLIT.split(text)]
    return [p for p in parts if len(p) > 3]


def tokens(text: str) -> list[str]:
    return [w for w in WORD_RE.findall(text.lower()) if w not in STOPWORDS]


def lexical_overlap(a: str, b: str) -> float:
    """Share of a's content words that also appear in b."""
    ta = set(tokens(a))
    if not ta:
        return 0.0
    return len(ta & set(tokens(b))) / len(ta)


def jaccard(a: str, b: str) -> float:
    ta, tb = set(tokens(a)), set(tokens(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def phrase_regex(phrases: list[str]) -> re.Pattern | None:
    if not phrases:
        return None
    return re.compile(r"(?<![\w])(?:" + "|".join(phrases) + r")(?![\w])", re.IGNORECASE)
