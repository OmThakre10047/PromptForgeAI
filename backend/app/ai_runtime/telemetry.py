import json
from pathlib import Path

class Telemetry:
    FILE = Path("telemetry.json")

    def __init__(self):

        if self.FILE.exists():

            self.data = json.loads(self.FILE.read_text())
        
        else:

            self.data = {}

    def save(self):

        self.FILE.write_text(
            json.dumps(
                self.data,
                indent=4,
            )
        )
    
    def record_success(
        self,
        model,
        latency,
    ):
        
        info = self.data.setdefault(
            model,
            {
                "calls": 0,
                "success": 0,
                "failures": 0,
                "avg_latency": 0,
            }
        )

        info["calls"] += 1
        info["success"] += 1
        info["avg_latency"] = (
            info["avg_latency"] * (info["success"] - 1)
            + latency
        ) / info["success"]

        self.save()

    def record_failure(
        self,
        model,
    ):

        info = self.data.setdefault(
            model,
            {
                "calls": 0,
                "success": 0,
                "failures": 0,
                "avg_latency": 0,
            },
        )

        info["calls"] += 1
        info["failures"] += 1

        self.save()