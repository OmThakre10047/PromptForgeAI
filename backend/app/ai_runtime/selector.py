from app.ai_runtime.model import RuntimeModel
from app.ai_runtime.telemetry_loader import TelemetryLoader


class ModelSelector:

    @staticmethod
    def score(
        model: RuntimeModel,
        task: str,
    ) -> float:

        score = 0

        # Base score
        score += 30

        # Runtime health
        score += model.success_rate * 20
        score -= model.avg_latency

        # General quality
        score += model.quality_score * 2
        score += model.json_score

        if task == "planning":
            score += model.reasoning_score * 5
            score += model.speed_score * 2

        elif task == "coding":
            score += model.coding_score * 5
            score += model.reasoning_score * 2

        elif task == "review":
            score += model.reasoning_score * 5
            score += model.json_score * 3

        elif task == "repair":
            score += model.coding_score * 4
            score += model.reasoning_score * 4
        elif task == "testing":
            score += model.speed_score * 5
            score += model.json_score * 3
            score += model.reasoning_score * 1
        else:
            score += model.reasoning_score * 2

        if model.disabled:
            return -999

        return score
    
    @staticmethod
    def select(
        models,
        task,
        top_k=3,
    ):

        ranked = sorted(
            models,
            key=lambda model: ModelSelector.score(
                model,
                task,
            ),
            reverse=True,
        )

        ranked = [
            model
            for model in ranked
            if model.modality == "text->text"
            and not model.disabled
        ]

        if task == "testing":

            json_models = [
                m for m in ranked
                if m.supports_json
            ]

            if len(json_models) >= top_k:
                return json_models[:top_k]

            return ranked[:top_k]

        return ranked[:top_k]