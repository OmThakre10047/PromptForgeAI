import json
from pyexpat import model
from typing import Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

def normalize_hidden_tests(data):

    if "hidden_tests" not in data:
        return data

    for t in data["hidden_tests"]:

        if isinstance(t.get("input"), list):

            arr = t["input"]

            t["input"] = (
                f"{len(arr)}\n"
                + " ".join(map(str, arr))
            )

        if not isinstance(
            t.get("expected_output"),
            str,
        ):
            t["expected_output"] = str(
                t["expected_output"]
            )

    return data


def parse_json(data, model: Type[T]) -> T:

    if isinstance(data, model):
        return data

    if isinstance(data, dict):
        return model.model_validate(data)

    if isinstance(data, str):

        text = data.strip()

        # Remove markdown fences
        if text.startswith("```"):
            lines = text.splitlines()

            if lines:
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            text = "\n".join(lines).strip()

        # Extract JSON object if extra text exists
        start = text.find("{")
        end = text.rfind("}")

        if start != -1 and end != -1:
            text = text[start:end + 1]

        data = json.loads(text)

        # Normalize issues
        if isinstance(data, dict) and "issues" in data:

            normalized = []

            for issue in data["issues"]:

                if isinstance(issue, dict):
                    normalized.append(
                        issue.get("description")
                        or issue.get("message")
                        or str(issue)
                    )
                else:
                    normalized.append(str(issue))

            data["issues"] = normalized

                # Normalize planner sample tests
        if "sample_tests" in data:
            for test in data["sample_tests"]:
                test["input"] = str(test["input"])
                test["expected_output"] = str(test["expected_output"])
        data = normalize_hidden_tests(data)
        return model.model_validate(data)

    raise TypeError(f"Unsupported type: {type(data)}")