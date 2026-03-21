import re


_WHITESPACE_RE = re.compile(r"\s+")


def normalize_skill_name(value: str | None) -> str:
    if not value:
        return ""
    normalized = _WHITESPACE_RE.sub(" ", value.strip())
    return normalized.lower()
