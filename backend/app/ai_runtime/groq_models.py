from app.ai_runtime.model import RuntimeModel
from app.ai_runtime.capability_scorer import CapabilityScorer


def get_groq_models():

    models = [

        RuntimeModel(
            id="llama-3.3-70b-versatile",
            name="Groq: Llama 3.3 70B",
            provider="groq",
            context_length=131072,
            supports_json=True,
            supports_tools=True,
            supports_reasoning=True,
            free=True,
            coding_score=9,
            reasoning_score=9,
            json_score=9,
            speed_score=10,
            quality_score=9,
        ),

        RuntimeModel(
            id="qwen/qwen3-32b",
            name="Groq: Qwen3 32B",
            provider="groq",
            context_length=131072,
            supports_json=True,
            supports_tools=True,
            supports_reasoning=True,
            free=True,
            coding_score=9,
            reasoning_score=9,
            json_score=9,
            speed_score=10,
            quality_score=9,
        ),

        RuntimeModel(
            id="deepseek-r1-distill-llama-70b",
            name="Groq: DeepSeek R1 Distill",
            provider="groq",
            context_length=131072,
            supports_json=True,
            supports_tools=True,
            supports_reasoning=True,
            free=True,
            coding_score=9,
            reasoning_score=10,
            json_score=9,
            speed_score=10,
            quality_score=10,
        ),
    ]

    return [CapabilityScorer.score(m) for m in models]