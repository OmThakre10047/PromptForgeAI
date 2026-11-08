import json
from pathlib import Path


class ModelRegistry:

    def __init__(self):

        registry_file = (
            Path(__file__).parent / "models.json"
        )

        with open(registry_file, "r", encoding="utf-8") as f:

            self.models = json.load(f)

    def get_all_models(self):

        return self.models

    def get_enabled_models(self):

        return [

            model

            for model in self.models

            if model["enabled"]

        ]

    def get_models_by_role(self, role):

        return [

            model

            for model in self.models

            if role in model["roles"]
            and model["enabled"]

        ]