from dataclasses import asdict, dataclass


@dataclass
class RuntimeModel:
    """A model the router can choose from, with static capability priors (0-10+)."""

    id: str
    name: str
    provider: str
    context_length: int = 0

    supports_json: bool = False
    supports_tools: bool = False
    supports_reasoning: bool = False
    free: bool = True
    modality: str = "text->text"

    coding_score: float = 5.0
    reasoning_score: float = 5.0
    json_score: float = 5.0
    speed_score: float = 5.0
    quality_score: float = 5.0

    disabled: bool = False

    def to_dict(self) -> dict:
        return asdict(self)
