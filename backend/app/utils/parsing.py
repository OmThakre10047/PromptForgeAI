"""Robust extraction of JSON and source code from raw LLM output."""

from __future__ import annotations

import json
import re
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

_FENCE = re.compile(r"```([a-zA-Z0-9_+#-]*)[ \t]*\n(.*?)```", re.DOTALL)
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


class ParseError(ValueError):
    pass


def strip_reasoning(text: str) -> str:
    """Remove <think>...</think> blocks emitted by some reasoning models."""
    return _THINK.sub("", text or "").strip()


def _balanced_objects(text: str):
    """Yield every top-level balanced {...} substring, respecting strings."""
    depth, start, in_str, esc = 0, None, False, False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                yield text[start:i + 1]
                start = None


def _loads_lenient(blob: str):
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        # Common LLM slip: trailing commas.
        return json.loads(re.sub(r",\s*([}\]])", r"\1", blob))


def extract_json(text: str) -> dict:
    text = strip_reasoning(text)
    candidates = [body for _, body in _FENCE.findall(text)] + [text]
    for chunk in candidates:
        objects = sorted(_balanced_objects(chunk), key=len, reverse=True)
        for blob in objects:
            try:
                data = _loads_lenient(blob)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                return data
    raise ParseError("No valid JSON object found in model output")


def parse_model(text: str, model: Type[T], aliases: dict[str, str] | None = None) -> T:
    data = extract_json(text)
    for src, dst in (aliases or {}).items():
        if src in data and dst not in data:
            data[dst] = data.pop(src)
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ParseError(f"JSON did not match {model.__name__}: {exc.errors()[:3]}") from exc


LANG_TAGS = {
    "cpp": {"cpp", "c++", "cc", "cxx", "c"},
    "python": {"python", "py", "python3"},
}


def extract_code(text: str, language: str) -> str:
    """Pick the most plausible code block for `language` from an LLM answer."""
    text = strip_reasoning(text)
    blocks = _FENCE.findall(text)
    if blocks:
        tagged = [body for tag, body in blocks if tag.lower() in LANG_TAGS.get(language, set())]
        pool = tagged or [body for _, body in blocks]
        return max(pool, key=len).strip()

    # Unterminated fence ("```cpp\n...") - take everything after it.
    m = re.search(r"```[a-zA-Z0-9_+#-]*[ \t]*\n(.*)", text, re.DOTALL)
    if m:
        return m.group(1).strip()

    if language == "cpp":
        # Drop leading prose before the first preprocessor line / using / code token.
        m = re.search(r"^(#include|#define|#pragma|using |int main|template|typedef|struct |class )", text, re.MULTILINE)
        if m:
            return text[m.start():].strip()
    return text.strip()
