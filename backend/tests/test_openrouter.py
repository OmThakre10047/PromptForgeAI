from openai import OpenAI
from app.core.config import settings

client = OpenAI(
    api_key=settings.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)

response = client.chat.completions.create(
    model="nvidia/nemotron-3-super-120b-a12b:free",
    messages=[
        {
            "role": "user",
            "content": "Reply with exactly: PromptForge Working"
        }
    ],
)

print(response.choices[0].message.content)