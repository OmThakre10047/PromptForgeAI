from app.ai_runtime.model import RuntimeModel


class CapabilityScorer:

    @staticmethod
    def score(model: RuntimeModel):

        # ---------- Base ----------
        model.coding_score = 5.0
        model.reasoning_score = 5.0
        model.json_score = 5.0
        model.speed_score = 5.0
        model.quality_score = 5.0

        name = model.name.lower()
        model_id = model.id.lower()

        # ---------- Coding ----------
        if any(x in name for x in [
            "code",
            "coder",
            "coding",
            "laguna",
        ]):
            model.coding_score += 4

        if "glm" in name:
            model.coding_score += 3
            model.reasoning_score += 3

        if "minimax" in name:
            model.coding_score += 2
            model.reasoning_score += 3

        if "nemotron" in name:
            model.coding_score += 1
            model.reasoning_score += 3

        # ---------- Reasoning ----------
        if model.supports_reasoning:
            model.reasoning_score += 4

        if "reason" in name:
            model.reasoning_score += 2

        if "glm" in name:
            model.reasoning_score += 2

        if "minimax" in name:
            model.reasoning_score += 2

        # ---------- JSON ----------
        if model.supports_json:
            model.json_score += 4

        # ---------- Quality ----------
        if model.context_length >= 128000:
            model.quality_score += 2

        if model.context_length >= 1000000:
            model.quality_score += 2

        # ---------- Speed ----------
        if "lightning" in name:
            model.speed_score += 4

        if "flash" in name:
            model.speed_score += 4

        if "nano" in name:
            model.speed_score += 5

        if "mini" in name:
            model.speed_score += 2

        if "xs" in name:
            model.speed_score += 2

        # ---------- Known model adjustments ----------
        # These are based on the models currently available
        # in our free OpenRouter pool.

        if "laguna-s-2.1" in model_id:
            model.coding_score += 3

        if "laguna-xs-2.1" in model_id:
            model.coding_score += 2

        if "north-mini-code" in model_id:
            model.coding_score += 2

        return model