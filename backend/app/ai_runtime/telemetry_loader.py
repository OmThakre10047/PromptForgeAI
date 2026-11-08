import json
from pathlib import Path

class TelemetryLoader:

    FILE = Path("telemetry.json")

    @classmethod
    def load(cls):

        if not cls.FILE.exists():
            return {}
        
        return json.loads(cls.FILE.read_text())