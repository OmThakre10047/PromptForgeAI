from pathlib import Path


class PromptLoader:

    PROMPT_DIR = Path(__file__).parent.parent / "prompts"

    @staticmethod
    def load(name: str) -> str:
        file = PromptLoader.PROMPT_DIR / f"{name}.txt"

        with open(file, "r", encoding="utf-8") as f:
            return f.read()