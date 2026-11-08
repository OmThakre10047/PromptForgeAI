from app.ai_runtime.runtime import AIRuntime

runtime = AIRuntime()
runtime.initialize()
models = runtime.get_models()
print()
print(f"Models Loaded: {len(models)}")
print()
print(models[0])