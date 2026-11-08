from app.ai_runtime.providers.openrouter_provider import OpenRouterProvider
from app.ai_runtime.providers.groq_provider import GroqProvider


PROVIDERS = {
    
    "openrouter": OpenRouterProvider(),
    "groq": GroqProvider(),    
}