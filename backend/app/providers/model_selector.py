from app.providers.model_registry import MODELS


class ModelSelector:

    @staticmethod
    def get_models(task: str):

        # First preference: exact task match
        preferred = [
            model
            for model in MODELS
            if model.purpose == task and model.active
        ]

        # Second preference: general models
        general = [
            model
            for model in MODELS
            if model.purpose == "general" and model.active
        ]

        # Remove duplicates
        result = []

        for model in preferred + general:
            if model not in result:
                result.append(model)

        return result