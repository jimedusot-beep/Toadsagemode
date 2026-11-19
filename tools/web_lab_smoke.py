"""Opt-in live WebKit containment sanity check; NEVER run in GitHub Actions.

This script uses only a fixed known-safe test site and the separate
restricted browser Docker worker. No model-generated source is executed.
It cannot certify a host against adversarial browser escapes.
"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from toad_core.web_lab import WebKitDockerWorker


def fixture():
    return {
        "schema":"toad-web-source-draft-v1",
        "name":"known-harmless-smoke",
        "title":"Known Harmless Smoke",
        "files":[
            {"path":"index.html","content":"<!doctype html><html><head><title>Known Harmless Smoke</title><script src='app.js' defer></script></head><body><button id='flip'>Front</button></body></html>"},
            {"path":"styles.css","content":"body{color:green}"},
            {"path":"app.js","content":"document.getElementById('flip').addEventListener('click', () => {document.getElementById('flip').textContent='Back';});"},
        ],
        "declared_features":["flip a button"],
    }


def run():
    worker=WebKitDockerWorker()
    available=worker.availability()
    if not available["available"]:
        return {"live_verified":False,"blocked":available["reason"],"probes":[]}
    normal=worker.run_web_source(fixture(),[
        {"kind":"title","expected":"Known Harmless Smoke"},
        {"kind":"click_text","selector":"#flip","target":"#flip","contains":"Back"},
    ])
    # A nonmatching frozen expectation MUST be reported as failed, not green.
    negative=worker.run_web_source(fixture(),[
        {"kind":"title","expected":"This title should not exist"},
    ])
    good=(
        normal["passed"] and normal["executed"] and normal["cleanup_ok"] and
        not negative["passed"] and negative["executed"] and negative["cleanup_ok"] and
        normal["image_id"] == negative["image_id"]
    )
    return {
        "live_verified":bool(good),
        "probes":[
            {"kind":"known_harmless_interaction","passed":bool(normal["passed"]),"record":normal},
            {"kind":"negative_control","rejected":not negative["passed"],"record":negative},
        ],
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--run",action="store_true",help="Explicit local Docker execution of fixed trusted checks")
    args=parser.parse_args()
    if not args.run:
        parser.error("Pass --run on a trusted local Docker host; never GitHub Actions")
    result=run()
    print(json.dumps(result,indent=2))
    return 0 if result["live_verified"] else (2 if "blocked" in result else 1)


if __name__=="__main__":
    raise SystemExit(main())
