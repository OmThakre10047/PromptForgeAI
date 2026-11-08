from groq import AsyncGroq

from app.core.config import settings
from app.providers.base_provider import BaseProvider


class GroqProvider(BaseProvider):

    def __init__(self):
        self.client = AsyncGroq(
            api_key=settings.GROQ_API_KEY,
        )

    async def generate(
        self,
        system_prompt,
        user_prompt,
        model,
    ):

        response = await self.client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
        )

        return response.choices[0].message.content