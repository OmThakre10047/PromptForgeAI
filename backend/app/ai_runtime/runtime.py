from app.ai_runtime.cache import ModelCache
from app.ai_runtime.discovery import ModelDiscovery
from app.ai_runtime.groq_models import get_groq_models

class AIRuntime:

    _instance = None

    def __new__(cls):

        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.models = []
        return cls._instance
    
    def initialize(self):
        if self.models:
            return
        
        print("\nInitializing AI Runtime...")

        cached = ModelCache.load()

        if cached:
            print(f"Loaded {len(cached)} models from cache.")

            self.models = (
                ModelDiscovery.convert(cached)
                + get_groq_models()
            )

            return
        
        print("Cache empty.")

        raw_models = ModelDiscovery.fetch()
        free_models = ModelDiscovery.filter_free_models(raw_models)

        ModelCache.save(free_models)

        self.models = (
            ModelDiscovery.convert(free_models)
            + get_groq_models()
        )

        print(f"Loaded {len(self.models)} models.")

    def get_models(self):
        return self.models