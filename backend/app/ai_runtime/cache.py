import json
from pathlib import Path

CACHE_FILE = (
    Path(__file__).resolve().parents[2]
    / "cache"
    / "models.json"
)

class ModelCache:

    @staticmethod
    def load():

        if not CACHE_FILE.exists():
            return[]
        
        with open(CACHE_FILE,"r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("models", [])
        
    @staticmethod
    def save(models):

        CACHE_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "last_updated": None,
                    "models": models,
                },
                f,
                indent=4,
            )
    