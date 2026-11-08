import json
from pathlib import Path
from dataclasses import asdict, is_dataclass
from pydantic import BaseModel


class HistoryService:

    FILE = Path("history.json")

    @staticmethod
    def _serialize(obj):
        """
        Recursively convert anything into JSON serializable objects.
        """

        if obj is None:
            return None

        if isinstance(obj, (str, int, float, bool)):
            return obj

        if isinstance(obj, BaseModel):
            return HistoryService._serialize(obj.model_dump())

        if is_dataclass(obj):
            return HistoryService._serialize(asdict(obj))

        if isinstance(obj, dict):
            return {
                k: HistoryService._serialize(v)
                for k, v in obj.items()
            }

        if isinstance(obj, list):
            return [
                HistoryService._serialize(x)
                for x in obj
            ]

        if isinstance(obj, tuple):
            return [
                HistoryService._serialize(x)
                for x in obj
            ]

        if hasattr(obj, "__dict__"):
            return HistoryService._serialize(vars(obj))

        return str(obj)

    @classmethod
    def save(cls, state):

        history = []

        if cls.FILE.exists():
            try:
                history = json.loads(cls.FILE.read_text())
            except Exception:
                history = []

        record = {
            "problem": state.get("problem"),
            "status": state.get(
                "status",
                state.get("final_status")
            ),
            "plan": cls._serialize(state.get("plan")),
            "solution": cls._serialize(state.get("solution")),
            "execution": cls._serialize(state.get("execution")),
            "review": cls._serialize(state.get("review")),
            "trace": cls._serialize(state.get("trace")),
        }

        history.append(record)

        cls.FILE.write_text(
            json.dumps(history, indent=2)
        )