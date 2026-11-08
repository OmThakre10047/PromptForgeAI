from app.ai_runtime.cache import ModelCache


models = [
    {
        "id": 1,
        "name": "gemma"
    },
    {
        "id": 2,
        "name": "llama"
    }
]

ModelCache.save(models)

loaded = ModelCache.load()

print(loaded)