import asyncio

from app.services.llm import LLMService


async def main() -> None:
    client = LLMService().client
    assert client is not None
    models = [model.id async for model in client.models.list()]
    for model in sorted(models):
        if model.startswith(("gpt", "o3", "o4")):
            print(model)


asyncio.run(main())
