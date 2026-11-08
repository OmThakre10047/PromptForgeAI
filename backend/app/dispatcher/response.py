from dataclasses import dataclass

@dataclass
class ModelResponse:
    model_id: str
    output: str
    latency: float
    success: bool