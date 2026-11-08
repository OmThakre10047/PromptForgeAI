"""Heuristic capability priors for models we know nothing else about.

These are only *priors*: the router blends them with live telemetry
(success rate, latency, output quality, downstream reward) so a model with a
flattering name but poor real-world behaviour quickly drops in the ranking.
"""

from app.llm.model import RuntimeModel


class CapabilityScorer:

    @staticmethod
    def score(model: RuntimeModel) -> RuntimeModel:
        name = f"{model.id} {model.name}".lower()

        coding = reasoning = json_s = speed = quality = 5.0

        if any(k in name for k in ("code", "coder", "coding", "laguna", "devstral")):
            coding += 4
        if "glm" in name:
            coding += 3
            reasoning += 5
        if "minimax" in name:
            coding += 2
            reasoning += 5
        if "nemotron" in name:
            coding += 1
            reasoning += 3
        if any(k in name for k in ("deepseek", "qwen", "gpt-oss", "llama-3.3")):
            coding += 2
            reasoning += 2
        if "reason" in name or "r1" in name.split("-"):
            reasoning += 2

        if model.supports_reasoning:
            reasoning += 3
        if model.supports_json:
            json_s += 4

        if model.context_length >= 128_000:
            quality += 2
        if model.context_length >= 1_000_000:
            quality += 2
        if any(k in name for k in ("ultra", "70b", "120b", "550b")):
            quality += 2

        for key, bonus in (("lightning", 4), ("flash", 4), ("nano", 5), ("mini", 2), ("xs", 2), ("2.6b", 4)):
            if key in name:
                speed += bonus
        if any(k in name for k in ("ultra", "550b")):
            speed -= 2
        # Tiny models are fast but weak.
        if any(k in name for k in ("2.6b", "nano")):
            coding -= 2
            reasoning -= 2
            quality -= 2

        if "laguna-s-2.1" in name:
            coding += 3
        if "laguna-xs-2.1" in name:
            coding += 2
        if "north-mini-code" in name:
            coding += 2

        model.coding_score = coding
        model.reasoning_score = reasoning
        model.json_score = json_s
        model.speed_score = speed
        model.quality_score = quality
        return model
