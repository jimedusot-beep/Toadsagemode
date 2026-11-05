"""Run from a Toad Sage checkout with python tools/skill_pipeline_demo.py."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

def main():
    root = Path.cwd()
    fixture = root / "examples/hello.json"
    if not fixture.is_file():
        raise SystemExit("Run from the checkout containing examples/hello.json")
    with tempfile.TemporaryDirectory(prefix="toad-demo-") as workspace:
        def cli(*args, allowed=(0,)):
            run = subprocess.run([sys.executable, "-m", "toad_core", "--workspace", workspace, *args],
                                 check=False, text=True, stdout=subprocess.PIPE)
            if run.returncode not in allowed:
                print(run.stdout, file=sys.stderr)
                raise SystemExit(run.returncode)
            return json.loads(run.stdout)

        candidate = cli("ingest", str(fixture))
        identifier = candidate["id"]
        print(json.dumps(cli("inspect", identifier), indent=2))
        worker = cli("lab", "status", allowed=(0, 2))
        if not worker.get("available"):
            print(json.dumps(worker, indent=2))
            return 2
        report = cli("test", identifier)
        print(json.dumps(report, indent=2))
        if not report.get("passed"):
            return 1
        print("Review this candidate and the Docker test report before activation.")
        if not sys.stdin.isatty() or input("Type the candidate ID to approve: ").strip() != identifier:
            return 3
        print(json.dumps(cli("library", "install", identifier), indent=2))
        print(json.dumps(cli("library", "active"), indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
