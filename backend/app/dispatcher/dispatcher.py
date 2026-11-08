import time

from app.dispatcher.response import ModelResponse

class MultiModelDispatcher:

    def __init__(self, registry):
        self.registry = registry

    async def dispatch(self, provider,  prompt, role = "developer") -> list[ModelResponse]:
        models = self.registry.get_models_by_role(role)
        responses = []

        for model in models:
            start = time.time()
            
            try:
                result = await provider.generate(
                    system_prompt="",
                    user_prompt=prompt,
                    model=model["model"]
                )
                success = True
            except Exception as e:
                result = str(e)
                success = False
            
            latency = time.time() - start

            responses.append(ModelResponse(
                model_id=model["id"],
                output=result,
                latency=latency,
                success=success
            ))

        return responses