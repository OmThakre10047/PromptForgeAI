from app.registry.model_registry import ModelRegistry


registry = ModelRegistry()

print()

print("All Models")

print(registry.get_all_models())

print()

print("Developer Models")

print(registry.get_models_by_role("developer"))

print()

print("Reviewer Models")

print(registry.get_models_by_role("reviewer"))