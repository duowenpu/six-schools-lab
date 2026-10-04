"""Omnigent policy callables for the lab.

Each factory returns an evaluator ``event -> response | None`` following the
Omnigent policy contract (``{"result": "ALLOW" | "DENY" | "ASK", "reason": ...}``).
Returning ``None`` abstains. Policies are declared in each agent's config.yaml
under ``guardrails.policies`` and are enforced by the orchestration layer.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_PREFIXES = ("mcp__omnigent__", "functions.", "mcp__")


def _tool_name(event) -> str:
    data = event.get("data") or {}
    name = str(data.get("name") or event.get("target") or "")
    for p in _PREFIXES:
        if name.startswith(p):
            name = name[len(p):]
    return name


def _log(kind: str, event, verdict: str, agent: str = "") -> None:
    try:
        p = ROOT / "records" / "policy_log.jsonl"
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "policy": kind, "agent": agent,
                                "tool": _tool_name(event), "verdict": verdict}) + "\n")
    except OSError:
        pass


def make_allowlist(agent: str, allowed: list[str], allowed_prefixes: list[str] | None = None):
    """P1 / P6: an agent may only call the tools on its allowlist (tool permissions).

    Blind readers get nothing but ``get_blind_batch`` / ``submit_probe``; no agent
    gets shell or file tools, so nothing reaches the corpus metadata or the frozen
    taxonomies except through the audited lab tools.
    """
    allow = set(allowed)
    prefixes = tuple(allowed_prefixes or ())

    def evaluate(event):
        if event.get("type") != "tool_call":
            return None
        name = _tool_name(event)
        if name in allow or (prefixes and name.startswith(prefixes)):
            return {"result": "ALLOW"}
        _log("allowlist", event, "DENY", agent)
        return {"result": "DENY", "reason": f"LAB_POLICY_P1: tool {name!r} is not on the allowlist of agent {agent!r}"}

    return evaluate


def make_instrument_gate(tool: str = "request_publication"):
    """P3: no conclusion may be published unless the instrument passed validation (H-C2)."""

    def evaluate(event):
        if event.get("type") != "tool_call" or _tool_name(event) != tool:
            return None
        p = ROOT / "records" / "VALIDATION_STATUS"
        status = p.read_text().strip() if p.exists() else "NOT_RUN"
        if status == "PASS":
            return None  # abstain: the human-approval policy decides next
        _log("instrument_gate", event, "DENY")
        return {"result": "DENY", "reason": f"LAB_POLICY_P3: instrument validation status is {status}; "
                                            "run the pre-registered 'defectors' experiment and pass it before publishing"}

    return evaluate


def make_human_approval(tools: list[str], reason: str = "LAB_POLICY_P5: consequential action needs human approval"):
    """P5: consequential actions pause for a human decision in the Omnigent UI."""
    gated = set(tools)

    def evaluate(event):
        if event.get("type") != "tool_call" or _tool_name(event) not in gated:
            return None
        _log("human_approval", event, "ASK")
        return {"result": "ASK", "reason": reason}

    return evaluate


def make_file_gate(flag_file: str, sentinel: str = "GATE"):
    """Generic gate used by the smoke tests: deny every tool call unless ``flag_file`` contains PASS."""

    def evaluate(event):
        if event.get("type") != "tool_call":
            return None
        p = Path(flag_file)
        status = p.read_text().strip() if p.exists() else "MISSING"
        if status == "PASS":
            return {"result": "ALLOW"}
        return {"result": "DENY", "reason": f"{sentinel}: gate status={status}"}

    return evaluate
