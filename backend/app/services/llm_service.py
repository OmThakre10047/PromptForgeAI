import time
import asyncio

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

        print("=" * 60)
        print("TASK:", task)
        print("Candidates:", len(candidates))

        for m in candidates:
            print(m.name, m.modality)

        print("=" * 60)

        last_exception = None

        for model in candidates:

            print(f"\nTrying {model.name}")
            start = time.perf_counter()

            try:

                # Get provider safely
                provider = PROVIDERS.get(
                    model.provider.lower()
                )

                if provider is None:
                    raise Exception(
                        f"No provider registered for "
                        f"{model.provider}"
                    )

                print("Sending request...")

                response = await asyncio.wait_for(
                    provider.generate(
                        model=model.id,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                    ),
                    timeout=35,
                )

                latency = time.perf_counter() - start

                if response is None:
                    raise Exception(
                        f"{model.name} returned None"
                    )

                print(
                    f"✓ {model.name} completed "
                    f"in {latency:.2f}s"
                )

                self.telemetry.record_success(
                    model.name,
                    latency,
                )

                return {
                    "model": model.id,
                    "response": response,
                }

            except asyncio.TimeoutError:

                latency = time.perf_counter() - start

                print(
                    f"✗ {model.name} timed out "
                    f"after {latency:.2f}s"
                )

                self.telemetry.record_failure(
                    model.name
                )

                last_exception = Exception(
                    f"{model.name} timed out"
                )

                continue

            except Exception as e:

                latency = time.perf_counter() - start

                print(
                    f"✗ {model.name} failed "
                    f"after {latency:.2f}s"
                )

                print(
                    f"Error: {type(e).__name__}: {e}"
                )

                self.telemetry.record_failure(
                    model.name
                )

                last_exception = e

                continue

        raise Exception(
            f"All candidate models failed.\n"
            f"Last error: {last_exception}"
        )