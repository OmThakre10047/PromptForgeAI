from openai import RateLimitError

from app.providers.openrouter_provider import OpenRouterProvider
from app.providers.model_selector import ModelSelector


class ProviderManager:

    def __init__(self):

        self.provider = OpenRouterProvider()

    async def generate(
        self,
        system_prompt,
        user_prompt,
        task="general",
    ):

        last_exception = None

        models = ModelSelector.get_models(task)

        for model in models:
            print(f"\nTask: {task}")
            print(f"\nTrying model: {model.name}")

            try:

                response = await self.provider.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=model.name,
                )

                print(f"Trying {model.name}")

                return {
                    "model": model.name,
                    "response": response,
                }

            except RateLimitError:

                print(f"Rate limited: {model.name}")

                last_exception = RateLimitError

                continue

            except Exception as e:

                print(f"Failed: {model}")

                print(e)

                last_exception = e

                continue

        raise Exception(
            f"All models failed.\nLast Error: {last_exception}"
        )