from litellm import completion
from app.core.config import settings

def generate_response(system_prompt: str, user_prompt:str):
    if not settings.OPENAI_API_KEY:
        return "No API key configured yet."
    
    response = completion(
        model="gpt-4.1-mini",
        api_key=settings.OPENAI_API_KEY,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response["choices"][0]["message"]["content"]