from openai import AsyncOpenAI
from openai import RateLimitError

from app.core.config import settings
from app.providers.base_provider import BaseProvider


class OpenRouterProvider(BaseProvider):

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            timeout = 30,
        )

    async def generate(
        self,
        system_prompt,
        user_prompt,
        model,
    ):

        try:
            print("Sending request...")
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            print("Request received")

            print("=" * 80)
            print(response)
            print("=" * 80)

            message = response.choices[0].message

            print("CONTENT:", message.content)
            print("REASONING:", getattr(message, "reasoning", None))
            print("TOOL CALLS:", getattr(message, "tool_calls", None))

            return message.content

        except RateLimitError:
            raise

        except Exception:
            raise