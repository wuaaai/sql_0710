from __future__ import annotations

import hashlib
import re
from typing import Iterable, List


SPACE_RE = re.compile(r"\s+")
LEADING_INDEX_RE = re.compile(r"^[0-9一二三四五六七八九十]+[、.．)]")


def normalize_text(text: str) -> str:
    if text is None:
        return ""
    value = text.strip().replace("\u3000", " ")
    value = value.replace("（", "(").replace("）", ")")
    value = value.replace("：", ":").replace("，", ",")
    value = SPACE_RE.sub("", value)
    value = value.replace("\n", "").replace("\r", "")
    value = LEADING_INDEX_RE.sub("", value)
    return value


def clean_text_block(text: str) -> str:
    if text is None:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def unique_list(values: Iterable[str]) -> List[str]:
    seen = set()
    output: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def stable_id(*parts: str) -> str:
    raw = "||".join(parts)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()
