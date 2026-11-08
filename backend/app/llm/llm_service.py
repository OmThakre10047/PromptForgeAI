from openai import RateLimitError
import time

from app.ai_runtime.runtime import AIRuntime
from app.ai_runtime.selector import ModelSelector
from app.ai_runtime.telemetry import Telemetry
from app.ai_runtime.provider_registry import PROVIDERS


class LLMService:

    def __init__(self):

        self.runtime = AIRuntime()
        self.runtime.initialize()

        self.telemetry = Telemetry()

    async def generate(
        self,
        system_prompt,
        user_prompt,
        task="general",
    ):

        models = self.runtime.get_models()

        candidates = ModelSelector.select(
            models=models,
            task=task,
        )

        last_exception = None

        for model in candidates:

            print(f"\nTrying {model.name}")

            # This is the ONLY new part
            provider = PROVIDERS[model.provider]

            try:

                start = time.perf_counter()

                response = await provider.generate(
                    model=model.id,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )

                latency = time.perf_counter() - start

                self.telemetry.record_success(
                    model.name,
                    latency,
                )

                return {
                    "model": model.id,
                    "response": response,
                }

            except RateLimitError as e:

                self.telemetry.record_failure(model.name)
                last_exception = e

            except Exception as e:

                self.telemetry.record_failure(model.name)
                print(e)
                last_exception = e

        raise Exception(
            f"All candidate models failed.\nLast error: {last_exception}"
        )