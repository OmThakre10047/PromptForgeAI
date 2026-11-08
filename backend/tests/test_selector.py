from app.ai_runtime.runtime import AIRuntime
from app.ai_runtime.selector import ModelSelector

runtime = AIRuntime()
runtime.initialize()

models = runtime.get_models()

tasks = [
    "planning",
    "coding",
    "review",
    "repair",
]

for task in tasks:

    print(f"\nTop {task.capitalize()} Models")
    print("-" * 50)

    ranked = ModelSelector.select(
        models=models,
        task=task,
        top_k=5,
    )

    for model in ranked:
        print(f"{model.name:<40} {ModelSelector.score(model, task):.2f}")