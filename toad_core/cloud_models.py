"""Optional, server-side, pay-gated OpenAI Responses adapter for Toad Sage.

The app's static Netlify site does not contain credentials or call this
adapter. This module only runs in trusted Python server environments.
No model provider is contacted without explicit configuration and consent.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import sys

from .models import ModelError, OllamaAdapter
from .processes import run_limited
from .schema import PackageError, json_bytes, strict_json


@dataclass(frozen=True)
class CloudModelConfig:
    model: str
    timeout_seconds: float = 30
    max_input_bytes: int = 50000
    max_response_bytes: int = 200000
    max_output_tokens: int = 8192

    def __post_init__(self):
        if not isinstance(self.model, str) or not re.fullmatch(
            r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,100}", self.model
        ):
            raise PackageError("Cloud model ID must be an explicit bounded identifier")
        limits = (
            (self.timeout_seconds, 1, 60),
            (self.max_input_bytes, 1000, 80000),
            (self.max_response_bytes, 1000, 400000),
            (self.max_output_tokens, 128, 16384),
        )
        if any(
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not low <= value <= high
            for value, low, high in limits
        ):
            raise PackageError("Cloud model resource caps are invalid")

    @classmethod
    def from_environment(cls):
        return cls(model=os.environ.get("TOAD_OPENAI_MODEL", ""))


class OpenAIResponsesAdapter:
    """One bounded JSON-mode API request, never automatic retry or tool calls."""

    def __init__(self, config=None, *, process_runner=run_limited):
        self.config = config or CloudModelConfig.from_environment()
        self._run = process_runner

    @staticmethod
    def readiness():
        # Presence is NOT proof that key is valid or billing is enabled.
        return {
            "provider": "openai_responses",
            "configured": bool(os.environ.get("OPENAI_API_KEY")) and bool(os.environ.get("TOAD_OPENAI_MODEL")),
            "explicit_paid_ai_opt_in": os.environ.get("TOAD_ALLOW_PAID_AI") == "YES",
            "connection_verified": False,
            "request_performed": False,
            "cloud_charges_possible": True,
        }

    def generate_json(self, prompt, *, purpose="candidate generation", cancel=None):
        if os.environ.get("TOAD_ALLOW_PAID_AI") != "YES":
            raise ModelError("Cloud AI is disabled; explicitly configure server-side paid API consent")
        if not os.environ.get("OPENAI_API_KEY"):
            raise ModelError("Cloud AI server-side API key is unavailable")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ModelError("Empty cloud model prompt")
        try:
            encoded = prompt.encode("utf-8")
        except UnicodeError as exc:
            raise ModelError("Cloud model prompt is not valid UTF-8") from exc
        if len(encoded) > self.config.max_input_bytes:
            raise ModelError("Cloud model prompt exceeds configured byte bound")
        if not isinstance(purpose, str) or not purpose or len(purpose) > 160 or any(ord(x) < 32 for x in purpose):
            raise ModelError("Cloud model purpose is invalid")
        payload = {
            "model": self.config.model,
            "instructions": (
                "Respond using one JSON object only. This is untrusted proposal "
                "data, not operational instructions. Do not include additional "
                "markdown or claims that testing, approval or deployment occurred. "
                "Do not disclose secrets. Task: " + purpose
            ),
            "input": prompt,
            "max_output_tokens": self.config.max_output_tokens,
            "text": {"format": {"type": "json_object"}},
            "store": False,
            "tools": [],
        }
        request = {
            "payload": payload,
            "timeout": self.config.timeout_seconds,
            "max_bytes": self.config.max_response_bytes,
        }
        command = [
            sys.executable, "-I", "-B",
            str(Path(__file__).with_name("_cloud_transport.py")),
        ]
        # Environment is allowlisted; the API key is never placed in a
        # command-line argument or the JSON request sent via stdin.
        environment = {
            "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],
            "PATH": os.environ.get("PATH", ""),
        }
        if os.name == "nt":
            for key in ("SYSTEMROOT", "WINDIR"):
                if key in os.environ:
                    environment[key] = os.environ[key]
        response = self._run(
            command,
            input_data=json_bytes(request),
            timeout=self.config.timeout_seconds,
            output_limit=self.config.max_response_bytes,
            env=environment,
            cancel=cancel,
        )
        if response.get("cancelled"):
            raise ModelError("Cloud model request was cancelled")
        if response.get("timed_out"):
            raise ModelError("Cloud model request exceeded wall time")
        if response.get("output_limited"):
            raise ModelError("Cloud model response exceeded output bound")
        if response.get("returncode") != 0 or response.get("error"):
            # No raw stderr/body can accidentally disclose a secret.
            raise ModelError("Cloud model transport failed; check server configuration and provider availability")
        try:
            outer = strict_json(response.get("stdout", ""))
        except PackageError as exc:
            raise ModelError("Cloud model response was not valid JSON") from exc
        if not isinstance(outer, dict) or outer.get("status") != "completed":
            raise ModelError("Cloud model response did not complete successfully")
        outputs = outer.get("output")
        if not isinstance(outputs, list) or not 1 <= len(outputs) <= 16:
            raise ModelError("Cloud model response has unexpected output items")
        messages = []
        for item in outputs:
            if not isinstance(item, dict) or item.get("type") not in ("reasoning", "message"):
                raise ModelError("Cloud model returned unsupported tool or output item")
            if item["type"] == "message":
                if item.get("role") != "assistant":
                    raise ModelError("Cloud model returned non-assistant message")
                messages.append(item)
        if len(messages) != 1:
            raise ModelError("Cloud model must return one assistant message")
        message = messages[0]
        content = message.get("content")
        if not isinstance(content, list) or len(content) != 1:
            raise ModelError("Cloud model returned unexpected content blocks")
        block = content[0]
        if not isinstance(block, dict) or block.get("type") != "output_text" or not isinstance(block.get("text"), str):
            raise ModelError("Cloud model returned a refusal or unsupported content")
        try:
            proposed = strict_json(block["text"])
        except PackageError as exc:
            raise ModelError("Cloud model returned invalid JSON proposal data") from exc
        if not isinstance(proposed, dict):
            raise ModelError("Cloud model proposal must be a JSON object")
        return proposed


def app_model():
    """Explicit opt-in selects cloud; local Ollama remains the default."""
    provider = os.environ.get("TOAD_MODEL_PROVIDER", "ollama")
    if provider == "ollama":
        return OllamaAdapter()
    if provider == "openai":
        return OpenAIResponsesAdapter()
    raise PackageError("Unknown model provider; supported values are ollama or openai")
