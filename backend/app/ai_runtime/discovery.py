import requests

from app.ai_runtime.cache import ModelCache
from app.core.config import settings
from app.ai_runtime.model import RuntimeModel
from app.ai_runtime.capability_scorer import CapabilityScorer

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


class ModelDiscovery:

    @staticmethod
    def fetch():

        print("Fetching OpenRouter models...")

        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"
        }

        response = requests.get(
            OPENROUTER_MODELS_URL,
            headers=headers,
            timeout=30,
        )

        response.raise_for_status()

        return response.json()["data"]

    @staticmethod
    def filter_free_models(models):

        free_models = []

        for model in models:

            pricing = model.get("pricing", {})

            try:
                prompt_price = float(pricing.get("prompt", 999))
                completion_price = float(
                    pricing.get("completion", 999)
                )
            except (TypeError, ValueError):
                continue

            if prompt_price != 0 or completion_price != 0:
                continue

            architecture = model.get("architecture", {})
            modality = architecture.get("modality", "")

            # We currently need text -> text models.
            if modality != "text->text":
                continue

            model_id = model.get("id", "").lower()
            model_name = model.get("name", "").lower()
            description = model.get("description", "").lower()

            combined = (
                model_id
                + " "
                + model_name
                + " "
                + description
            )

            # Exclude models that aren't useful for
            # programming/reasoning agents.
            excluded_keywords = [
                "lyria",
                "music",
                "audio",
                "speech",
                "tts",
                "whisper",
                "image",
                "imagen",
                "video",
                "veo",
                "stable diffusion",
                "flux",
                "content safety",
                "safety model",
                "moderation",
                "medical",
                "finance",
            ]

            if any(
                keyword in combined
                for keyword in excluded_keywords
            ):
                continue

            # Random router is not appropriate for our
            # deterministic multi-agent workflow.
            if model_id == "openrouter/free":
                continue

            free_models.append(model)

        print(
            f"Filtered {len(models)} free candidates "
            f"down to {len(free_models)} text models."
        )

        return free_models

    @staticmethod
    def convert(models):

        runtime_models = []

        for model in models:

            params = model.get(
                "supported_parameters",
                []
            )

            # Preserve OpenRouter's actual modality
            modality = model.get(
                "architecture",
                {}
            ).get(
                "modality",
                "text->text",
            )

            runtime_model = RuntimeModel(
                id=model["id"],
                name=model["name"],
                context_length=model.get(
                    "context_length",
                    0,
                ),
                provider="openrouter",

                modality=modality,

                supports_json=(
                    "structured_outputs" in params
                    or "response_format" in params
                ),

                supports_tools=(
                    "tools" in params
                ),

                supports_reasoning=(
                    "reasoning" in params
                    or "reasoning_effort" in params
                ),

                free=True,

                coding_score=5.0,
                reasoning_score=5.0,
                json_score=5.0,
                speed_score=5.0,
                quality_score=5.0,
            )

            runtime_model = CapabilityScorer.score(
                runtime_model
            )

            runtime_models.append(runtime_model)

        return runtime_models