"""Resolve SuperDev home, state dir, and operator.yaml.

Every SuperDev script imports this instead of hard-coding a person or repo.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SKILL_HOME = Path(__file__).resolve().parent.parent
OPERATOR_PATH = SKILL_HOME / "operator.yaml"
STATE = SKILL_HOME / "state"
INTENT = STATE / "user-intentions"
WORK_HISTORY = STATE / "work-history"
SESSION = STATE / "session.json"
SESSION_TTL = timedelta(hours=24)


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


def lane_dir() -> Path:
    """SHA-bound lane facts. Default: state/lane. Override with lane.dir or SUPERDEV_LANE."""
    raw = operator().get("lane") or {}
    path = ""
    if isinstance(raw, dict):
        path = str(raw.get("dir") or "")
    path = path or os.environ.get("SUPERDEV_LANE") or ""
    target = Path(path).expanduser() if path else STATE / "lane"
    target.mkdir(parents=True, exist_ok=True)
    return target


def worktree_parent() -> Path:
    raw = operator().get("workspace") or {}
    if isinstance(raw, dict) and raw.get("worktree_parent"):
        return Path(str(raw["worktree_parent"])).expanduser()
    return workspace().parent


def worktree_prefix() -> str:
    raw = operator().get("workspace") or {}
    if isinstance(raw, dict) and raw.get("worktree_prefix"):
        return str(raw["worktree_prefix"])
    return os.environ.get("SUPERDEV_WORKTREE_PREFIX") or ""


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


def _parse_bool(val: Any) -> bool | None:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        low = val.strip().lower()
        if low in {"true", "on", "1", "yes"}:
            return True
        if low in {"false", "off", "0", "no"}:
            return False
    return None


def load_session() -> dict[str, Any]:
    if not SESSION.exists():
        return {}
    try:
        data = json.loads(SESSION.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    raw_ts = data.get("updated_at")
    if raw_ts:
        try:
            ts = datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - ts > SESSION_TTL:
                SESSION.unlink(missing_ok=True)
                return {}
        except ValueError:
            pass
    return data


def set_auto_switch(on: bool, source: str = "chat") -> dict[str, Any]:
    ensure_state()
    data = {
        "auto_switch": bool(on),
        "source": source,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    SESSION.write_text(json.dumps(data, indent=2) + "\n")
    return data


def clear_session() -> bool:
    (lane_dir() / "focus.json").unlink(missing_ok=True)
    if SESSION.exists():
        SESSION.unlink()
        return True
    return False


def auto_switch(cli: str | None = None) -> tuple[bool, str]:
    """CLI on|off > session.json > operator.yaml routing.auto_switch > on."""
    if cli in {"on", "off"}:
        return cli == "on", "session"
    sess = load_session()
    if "auto_switch" in sess:
        parsed = _parse_bool(sess["auto_switch"])
        if parsed is not None:
            return parsed, "session"
    routing = operator().get("routing") or {}
    if isinstance(routing, dict) and "auto_switch" in routing:
        parsed = _parse_bool(routing["auto_switch"])
        if parsed is not None:
            return parsed, "operator.yaml"
    env = os.environ.get("SUPERDEV_AUTO_SWITCH", "").strip().lower()
    if env in {"on", "off", "true", "false", "1", "0"}:
        return env in {"on", "true", "1"}, "env"
    return True, "default"
