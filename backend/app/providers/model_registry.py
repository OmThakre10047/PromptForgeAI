from dataclasses import dataclass

@dataclass
class ModelInfo:

    name: str
    provider: str
    priority: int
    purpose: str
    max_tokens: int
    coding_score: int
    reasoning_score: int
    active: bool = True

MODELS = [
    ModelInfo(
        name="google/gemma-4-26b-a4b-it:free",
        provider="OpenRouter",
        priority=1,
        purpose="general",
        max_tokens=1200,
        coding_score=9,
        reasoning_score=9,
    ),

    ModelInfo(
        name="google/gemma-4-31b-it:free",
        provider="OpenRouter",
        priority=2,
        purpose="planning",
        max_tokens=1200,
        coding_score=9,
        reasoning_score=9,
    ),

    ModelInfo(
        name="meta-llama/llama-3.3-70b-instruct:free",
        provider="OpenRouter",
        priority=3,
        purpose="review",
        max_tokens=1200,
        coding_score=8,
        reasoning_score=8,
    ),

    ModelInfo(
        name="qwen/qwen3-coder:free",
        provider="OpenRouter",
        priority=4,
        purpose="coding",
        max_tokens=1200,
        coding_score=10,
        reasoning_score=8,
    ),
]