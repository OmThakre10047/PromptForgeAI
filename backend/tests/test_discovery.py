from app.ai_runtime.discovery import ModelDiscovery


models = ModelDiscovery.fetch()

free_models = ModelDiscovery.filter_free_models(
    models
)

runtime_models = ModelDiscovery.convert(
    free_models
)

print()

print(runtime_models[0])

print()

print(f"Total runtime models: {len(runtime_models)}")