import asyncio

from app.models.gemini_model import GeminiModel


async def main():

    model = GeminiModel()

    response = await model.generate(
        "Introduce yourself in one sentence."
    )

    print(response)


if __name__ == "__main__":
    asyncio.run(main())