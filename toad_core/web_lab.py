"""Opt-in WebKit Docker worker for untrusted AI-written web files.

The host never evals, imports, serves or executes candidate code. It streams
data to a disposable locally provisioned Linux Docker image. Real operation is
blocked unless the existing strict cgroup v2/default seccomp probe succeeds.
GitHub Actions must use policy/contract tests only, never run this worker.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from .lab import DockerWorker, LabPolicy
from .schema import PackageError, json_bytes, strict_json
from .web_codegen import validate_web_source

WEB_IMAGE = "toad-sage-webkit-lab:1"
CHECK_FIELDS = {
    "title": frozenset(("kind", "expected")),
    "text": frozenset(("kind", "selector", "contains")),
    "click_text": frozenset(("kind", "selector", "target", "contains")),
    "fill_click_text": frozenset(("kind", "input", "value", "button", "target", "contains")),
}
TMP_BYTES = 128 * 1024 * 1024


def validate_checks(checks):
    """Frozen declarative acceptance steps; NEVER execute caller-supplied JS."""
    if not isinstance(checks, list) or not 1 <= len(checks) <= 8:
        raise PackageError("Provide 1–8 declared browser acceptance checks")
    checked = []
    for spec in checks:
        if not isinstance(spec, dict) or not isinstance(spec.get("kind"), str):
            raise PackageError("Invalid browser check")
        expected = CHECK_FIELDS.get(spec["kind"])
        if expected is None or set(spec) != expected:
            raise PackageError("Unknown browser test operation or unexpected field")
        clean = {}
        for key, value in spec.items():
            if not isinstance(value, str) or len(value) > 250 or (key != "value" and not value.strip()):
                raise PackageError("Browser test field must be short text")
            if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
                raise PackageError("Browser test fields cannot contain control characters")
            if key in ("selector", "target", "input", "button"):
                # Bounded CSS selectors only; reject Playwright engine extensions
                # and selectors with complex state-dependent pseudos.
                if len(value) > 100 or not re.fullmatch(r"[#.]?[A-Za-z][A-Za-z0-9_#. -]*", value):
                    raise PackageError("Only simple CSS selectors are accepted")
            clean[key] = value
        checked.append(clean)
    if len(json_bytes(checked)) > 4000:
        raise PackageError("Browser acceptance tests exceed size limit")
    return checked


class WebKitDockerWorker(DockerWorker):
    """Separate browser container, never using the trusted CI Playwright runner."""

    def __init__(self):
        # Existing LabPolicy probe performs actual daemon/security capability
        # checks. 512 MiB is intentionally bounded and may be too small for
        # some browsers; a failing live smoke test remains BLOCKED.
        super().__init__(LabPolicy(
            image=WEB_IMAGE, timeout_seconds=30, output_bytes=64000,
            memory_mb=512, cpus=1, pids=64, disk_mb=64,
        ))

    def _create_args(self, name, image_id):
        p = self.policy
        return [
            "create", "--name", name, "--label=org.toad-sage.web-lab=1",
            "--interactive", "--pull=never", "--network=none", "--read-only",
            "--user=65532:65532", "--cap-drop=ALL",
            "--security-opt=no-new-privileges=true",
            "--pids-limit=" + str(p.pids),
            "--memory=" + str(p.memory_mb*1024*1024),
            "--memory-swap=" + str(p.memory_mb*1024*1024),
            "--cpus=" + str(p.cpus),
            "--tmpfs", "/work:rw,nosuid,nodev,noexec,size="+str(p.disk_mb*1024*1024)+",mode=1777",
            "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size="+str(TMP_BYTES)+",mode=1777",
            "--ipc=none", "--log-driver=none",
            "--ulimit", "nofile=64:64", "--ulimit", "nproc=64:64",
            "--ulimit", "fsize=8388608:8388608", "--ulimit", "core=0:0",
            "--hostname=toad-web-lab", "--env=HOME=/tmp",
            "--env=PLAYWRIGHT_BROWSERS_PATH=/ms-playwright",
            "--env=XDG_CACHE_HOME=/tmp", "--workdir=/work",
            "--entrypoint=/usr/bin/node", image_id,
            "/opt/toad-web/runner.cjs",
        ]

    def _check_container(self, data, image_id):
        """Check Docker's effective configuration, not just our arguments."""
        h = data.get("HostConfig") or {}
        c = data.get("Config") or {}
        p = self.policy
        expected = {
            "NetworkMode":"none", "ReadonlyRootfs":True, "Privileged":False,
            "PidsLimit":p.pids, "Memory":p.memory_mb*1024*1024,
            "MemorySwap":p.memory_mb*1024*1024,
            "NanoCpus":int(p.cpus*1e9), "IpcMode":"none",
        }
        if any(h.get(k) != v for k,v in expected.items()):
            raise PackageError("Browser container resource/isolation mismatch")
        if data.get("Image") != image_id:
            raise PackageError("Browser container image digest mismatch")
        if c.get("User") != "65532:65532" or c.get("WorkingDir") != "/work" or c.get("Entrypoint") != ["/usr/bin/node"]:
            raise PackageError("Browser container user or entrypoint mismatch")
        if c.get("Cmd") != ["/opt/toad-web/runner.cjs"]:
            raise PackageError("Browser container must run only the trusted harness")
        if h.get("Binds") or h.get("CapAdd") or h.get("Devices") or h.get("DeviceRequests") or h.get("Mounts"):
            raise PackageError("Browser container host mounts or elevated privileges forbidden")
        if set(h.get("CapDrop",[])) != {"ALL"}:
            raise PackageError("All browser container capabilities must be dropped")
        security = h.get("SecurityOpt",[])
        if not any(x in ("no-new-privileges=true","no-new-privileges") for x in security) or any("unconfined" in x for x in security):
            raise PackageError("Browser container security options mismatch")
        if h.get("LogConfig",{}).get("Type") != "none":
            raise PackageError("Browser container logging must be disabled")
        if any(m.get("Type") != "tmpfs" for m in data.get("Mounts",[])):
            raise PackageError("Browser worker cannot mount host files")
        tmpfs = h.get("Tmpfs",{})
        if set(tmpfs) != {"/work","/tmp"}:
            raise PackageError("Unexpected browser container writable paths")
        for loc,size in (("/work",p.disk_mb*1024*1024),("/tmp",TMP_BYTES)):
            if not isinstance(tmpfs[loc],str):
                raise PackageError("Missing browser writable filesystem restrictions")
            options = set(tmpfs[loc].split(","))
            if not {"rw","nosuid","nodev","noexec","size="+str(size)}.issubset(options):
                raise PackageError("Browser container writable tmpfs restrictions mismatch")
        env = c.get("Env",[])
        if not isinstance(env,list) or "HOME=/tmp" not in env or "PLAYWRIGHT_BROWSERS_PATH=/ms-playwright" not in env:
            raise PackageError("Unexpected browser environment")

    def run_web_source(self, source, checks, *, cancel=None):
        draft = validate_web_source(source)
        frozen = validate_checks(checks)
        source_digest = hashlib.sha256(json_bytes(draft)).hexdigest()
        checks_digest = hashlib.sha256(json_bytes(frozen)).hexdigest()
        result = {
            "schema":"toad-web-test-v1", "backend":"isolated_local_docker_webkit",
            "source_sha256":source_digest,"checks_sha256":checks_digest,
            "image_id":None,"executed":False,"passed":False,
            "cleanup_ok":True,"blocked_reason":None,
            "receipt":None,"policy":dict(self.policy.__dict__),
            "release_allowed":False,
        }
        if not self.docker:
            result["blocked_reason"] = "Local Docker is unavailable; no host/browser fallback"
            return result
        from tempfile import TemporaryDirectory
        try:
            with TemporaryDirectory(prefix="toad-web-docker-client-") as config:
                probe = self._probe(config)
                if not probe["available"]:
                    result["blocked_reason"] = probe["reason"]
                    return result
                result["image_id"] = probe["image_id"]
                name = "toad-web-lab-" + uuid.uuid4().hex
                try:
                    created = self._call(config, self._create_args(name, probe["image_id"]))
                    if not self._ok(created):
                        result["blocked_reason"] = "Could not create isolated browser container"
                        return result
                    inspected = self._inspect(config,name)
                    self._check_container(inspected,probe["image_id"])
                    payload = {
                        "schema":"toad-web-run-v1",
                        "files":draft["files"],
                        "checks":frozen,
                    }
                    run = self._call(
                        config,["start","--attach","--interactive",name],
                        input_data=json_bytes(payload),timeout=self.policy.timeout_seconds,
                        output_limit=self.policy.output_bytes,cancel=cancel,
                    )
                    state = self._inspect(config,name).get("State",{})
                    started = bool(state.get("StartedAt")) and not str(state.get("StartedAt")).startswith("0001-")
                    result["executed"] = started
                    result["timed_out"] = bool(run.get("timed_out"))
                    result["output_limited"] = bool(run.get("output_limited"))
                    result["oom_killed"] = bool(state.get("OOMKilled"))
                    try:
                        receipt = strict_json(run.get("stdout",""))
                        correct = (
                            isinstance(receipt,dict) and
                            receipt.get("schema") == "toad-web-browser-receipt-v1" and
                            receipt.get("browser") == "webkit" and
                            receipt.get("executed") is True and
                            receipt.get("passed") is True and
                            isinstance(receipt.get("checks"),list) and
                            len(receipt["checks"]) == len(frozen) and
                            all(isinstance(x,dict) and x == {
                                "index":i,"kind":s["kind"],"passed":True
                            } for i,(x,s) in enumerate(zip(receipt["checks"],frozen))) and
                            receipt.get("page_errors") == 0 and
                            isinstance(receipt.get("blocked_requests"),int)
                        )
                        if isinstance(receipt,dict):
                            result["receipt"] = {
                                "schema":receipt.get("schema"),"browser":receipt.get("browser"),
                                "passed":receipt.get("passed"),"checks":receipt.get("checks"),
                                "page_errors":receipt.get("page_errors"),
                                "blocked_requests":receipt.get("blocked_requests"),
                            }
                    except (PackageError, TypeError, ValueError, KeyError):
                        correct = False
                    result["passed"] = bool(
                        correct and self._ok(run) and started and
                        state.get("Running") is False and state.get("ExitCode") == 0 and
                        not state.get("OOMKilled") and not state.get("Error")
                    )
                    if not result["passed"]:
                        result["blocked_reason"] = "Browser tests failed or container exited abnormally"
                except (OSError, ValueError, PackageError):
                    result["blocked_reason"] = "Browser container setup/inspection failed"
                finally:
                    result["cleanup_ok"] = self._cleanup(config,name)
                    if not result["cleanup_ok"]:
                        result["passed"] = False
                        result["blocked_reason"] = "Browser container cleanup failed"
        except (OSError,ValueError,PackageError):
            result["blocked_reason"] = "Browser lab unavailable or failed"
        return result
