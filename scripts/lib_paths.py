"""Resolve SuperDev home, state dir, and operator.yaml.

Every SuperDev script imports this instead of hard-coding a person or repo.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

SKILL_HOME = Path(__file__).resolve().parent.parent
OPERATOR_PATH = SKILL_HOME / "operator.yaml"
STATE = SKILL_HOME / "state"
INTENT = STATE / "user-intentions"
WORK_HISTORY = STATE / "work-history"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text()
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text) or {}
        return data if isinstance(data, dict) else {}
    except ImportError:
        pass
    # Minimal fallback: "key: value" at most two levels. Enough to boot
    # without PyYAML. Nested maps from the example file still need PyYAML
    # for full fidelity — install.sh tells the operator.
    out: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(0, out)]
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if ":" not in raw:
            continue
        key, _, rest = raw.partition(":")
        key = key.strip()
        val = rest.strip()
        while stack and indent < stack[-1][0]:
            stack.pop()
        cur = stack[-1][1]
        if val in ("", "|", ">"):
            child: dict[str, Any] = {}
            cur[key] = child
            stack.append((indent + 2, child))
        else:
            if val in ("true", "True"):
                cur[key] = True
            elif val in ("false", "False"):
                cur[key] = False
            elif val in ("[]",):
                cur[key] = []
            else:
                cur[key] = val.strip('"').strip("'")
    return out


def operator() -> dict[str, Any]:
    return _load_yaml(OPERATOR_PATH)


def github_login() -> str:
    return str(operator().get("github", {}).get("login") or os.environ.get("SUPERDEV_GITHUB_LOGIN") or "")


def default_repo() -> str:
    return str(operator().get("github", {}).get("default_repo") or os.environ.get("SUPERDEV_DEFAULT_REPO") or "")


def workspace() -> Path:
    raw = operator().get("workspace", {})
    path = ""
    if isinstance(raw, dict):
        path = str(raw.get("path") or "")
    elif isinstance(raw, str):
        path = raw
    path = path or os.environ.get("SUPERDEV_WORKSPACE") or os.getcwd()
    return Path(path).expanduser()


def operator_name() -> str:
    op = operator().get("operator", {})
    if isinstance(op, dict):
        return str(op.get("name") or "the operator")
    return "the operator"


def ensure_state() -> None:
    INTENT.mkdir(parents=True, exist_ok=True)
    WORK_HISTORY.mkdir(parents=True, exist_ok=True)
