from openai import OpenAI
from openai import RateLimitError

from app.core.config import settings
from app.providers.base_provider import BaseProvider


class OpenRouterProvider(BaseProvider):

    def __init__(self):
        self.client = OpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
        )

    async def generate(
        self,
        system_prompt,
        user_prompt,
        model,
    ):

        try:

            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )

            return response.choices[0].message.content

        except RateLimitError:
            raise

        except Exception:
            raise