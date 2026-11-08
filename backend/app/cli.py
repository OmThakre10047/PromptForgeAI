"""Command-line runner.

    python -m app.cli problems/max_subarray.txt --language cpp
    python -m app.cli - < problem.txt
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.services.runs import RunService


async def _main(args) -> int:
    text = sys.stdin.read() if args.problem == "-" else Path(args.problem).read_text(encoding="utf-8")
    svc = RunService()
    result = None
    async for item in svc.stream(text, language=args.language, max_repairs=args.max_repairs):
        if item["type"] == "start":
            print(f"run {item['run_id']} ({item['language']}, mock={item['mock']})")
        elif item["type"] == "node":
            for e in item["events"]:
                if e["message"] != "done":
                    print(f"  {e['node']:>15} | {e['message']}")
        elif item["type"] == "result":
            result = item["result"]
    if result is None:
        return 2
    final = result["final"]
    print("\n" + "=" * 70)
    print(f"status: {final['status']}  tests: {final['passed']}/{final['total']}  score: {final['score']}  "
          f"repairs: {final['repair_attempts']}  replans: {final['replans']}")
    print(f"metrics: {json.dumps(result['metrics'])}")
    print("=" * 70)
    print(final["code"])
    if args.out:
        Path(args.out).write_text(final["code"], encoding="utf-8")
    return 0 if final["status"] in ("accepted", "passed") else 1


def main() -> None:
    p = argparse.ArgumentParser(description="PromptForge AI - solve a programming problem end to end")
    p.add_argument("problem", help="path to a problem statement file, or '-' for stdin")
    p.add_argument("--language", choices=["cpp", "python"], default=None)
    p.add_argument("--max-repairs", type=int, default=None)
    p.add_argument("--out", help="write the final solution to this file")
    sys.exit(asyncio.run(_main(p.parse_args())))


if __name__ == "__main__":
    main()
