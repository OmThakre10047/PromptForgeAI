from app.ai_runtime.runtime import AIRuntime

runtime = AIRuntime()
runtime.initialize()

models = runtime.get_models()

print(f"Models loaded: {len(models)}")

for model in models:
    print()
    print(model.name)
    print("Coding     :", model.coding_score)
    print("Reasoning  :", model.reasoning_score)
    print("JSON       :", model.json_score)
    print("Speed      :", model.speed_score)
    print("Quality    :", model.quality_score)