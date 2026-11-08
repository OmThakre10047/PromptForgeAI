"""OpenRouter and Groq both expose OpenAI-compatible chat completion APIs."""

from openai import APIStatusError, AsyncOpenAI, RateLimitError

from app.llm.providers.base import BaseProvider, ProviderError, ProviderResponse


class OpenAICompatibleProvider(BaseProvider):

    def __init__(self, name: str, api_key: str, base_url: str, timeout: float = 60.0):
        self.name = name
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=0)

    async def generate(self, model, system_prompt, user_prompt, max_tokens=4096, temperature=0.2):
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except RateLimitError as exc:
            raise ProviderError(str(exc), kind="rate_limit") from exc
        except APIStatusError as exc:
            kind = "rate_limit" if exc.status_code == 429 else "error"
            raise ProviderError(f"{exc.status_code}: {exc.message}", kind=kind) from exc

        if not response.choices:
            raise ProviderError(f"{model} returned no choices", kind="empty")

        content = (response.choices[0].message.content or "").strip()
        if not content:
            raise ProviderError(f"{model} returned empty content", kind="empty")

        usage = response.usage
        return ProviderResponse(
            content=content,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )


def openrouter_provider(api_key: str, timeout: float) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider("openrouter", api_key, "https://openrouter.ai/api/v1", timeout)


def groq_provider(api_key: str, timeout: float) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider("groq", api_key, "https://api.groq.com/openai/v1", timeout)
