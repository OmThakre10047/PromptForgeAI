from dataclasses import dataclass

@dataclass
class RuntimeModel:
    id: str
    name: str
    context_length: int
    provider: str

    supports_json: bool
    supports_tools: bool
    supports_reasoning: bool

    free: bool

    # <-- put it here
    modality: str = "text"

    coding_score: float = 5.0
    reasoning_score: float = 5.0
    json_score: float = 5.0
    speed_score: float = 5.0
    quality_score: float = 5.0

    score: float = 0.0
    success_rate: float = 1.0
    avg_latency: float = 0.0

    disabled: bool = False