#!/usr/bin/env python3
"""Preflight: is cursor-ide-browser actually available to this agent chat?

SuperDev Path 6 / smoke / pr-asset-upload require the built-in
`cursor-ide-browser` MCP. Cursor Browser UI can work while the agent
catalog is missing the server — that split has burned multiple Path 6
runs. This script diagnoses disk + (when possible) live gaps.

Usage:
  python3 ~/.cursor/skills/turbovets-superdev/scripts/browser_mcp_preflight.py
  python3 .../browser_mcp_preflight.py --project Users-hrishipotdar-Documents-platform
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HOME = Path.home()
CURSOR_PROJECTS = HOME / ".cursor" / "projects"
BUILTIN = "cursor-ide-browser"
APP_CONTROL = "cursor-app-control"


def project_dirs() -> list[Path]:
    if not CURSOR_PROJECTS.exists():
        return []
    return sorted(
        [p for p in CURSOR_PROJECTS.iterdir() if (p / "mcps").is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def inspect_project(project: Path) -> dict:
    mcps = project / "mcps"
    browser = mcps / BUILTIN
    tools_dir = browser / "tools"
    tools = sorted(p.stem for p in tools_dir.glob("*.json")) if tools_dir.is_dir() else []
    servers = sorted(p.name for p in mcps.iterdir() if p.is_dir()) if mcps.is_dir() else []
    return {
        "project": project.name,
        "has_browser_dir": browser.is_dir(),
        "has_app_control": (mcps / APP_CONTROL).is_dir(),
        "tool_count": len(tools),
        "tools_sample": tools[:8],
        "servers": servers,
    }


def default_project_name() -> str:
    # Prefer the platform workspace when present.
    preferred = "Users-hrishipotdar-Documents-platform"
    if (CURSOR_PROJECTS / preferred / "mcps").is_dir():
        return preferred
    dirs = project_dirs()
    return dirs[0].name if dirs else preferred


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--project",
        default=default_project_name(),
        help="Cursor projects/<name> folder (default: platform workspace)",
    )
    ap.add_argument("--pretty", action="store_true", default=True)
    ap.add_argument("--json", dest="as_json", action="store_true")
    args = ap.parse_args()

    project = CURSOR_PROJECTS / args.project
    this = inspect_project(project) if project.exists() else {
        "project": args.project,
        "error": "project dir missing",
    }
    peers = [inspect_project(p) for p in project_dirs()[:12]]
    peers_with_browser = [p for p in peers if p.get("has_browser_dir")]

    # Disk verdict for THIS project (agent chat may still differ — live
    # GetMcpTools is the source of truth inside a turn).
    disk_ok = bool(this.get("has_browser_dir") and this.get("tool_count", 0) > 0)

    gaps = []
    if not this.get("has_browser_dir"):
        gaps.append(
            "G1_DISK_MISSING: ~/.cursor/projects/<ws>/mcps/cursor-ide-browser "
            "is absent for this workspace. Built-in Browser MCP was never "
            "materialized here (or was dropped). Not fixable via mcp.json."
        )
    elif this.get("tool_count", 0) == 0:
        gaps.append(
            "G2_ZERO_TOOLS: browser dir exists but tools/=0 — known Cursor "
            "regression (catalog connected, no tools). Toggle Browser "
            "Automation Off→On, full quit Cursor, open a NEW agent chat."
        )

    if peers_with_browser and not disk_ok:
        names = ", ".join(p["project"] for p in peers_with_browser[:5])
        gaps.append(
            f"G3_WORKSPACE_SPLIT: other Cursor project folders HAVE "
            f"cursor-ide-browser ({names}) while this one does not. UI "
            "Browser history can still look healthy."
        )

    gaps.append(
        "G4_LIVE_CATALOG: disk ≠ live. Inside the agent turn, run "
        "GetMcpTools({pattern:'cursor-ide-browser|browser_navigate'}). "
        "Zero matches ⇒ agent cannot drive Browser even if you already "
        "logged into Cursor Browser. Start a new Agent chat after toggle."
    )
    gaps.append(
        "G5_CONTROL_PLANE: Settings → Tools & MCP → Browser Automation "
        "must be ON (Browser Tab). cursor-ide-browser never appears in "
        "mcp.json; ~/.cursor/mcp.json only holds user servers (fathom…)."
    )
    gaps.append(
        "G6_FEATURES_DISABLED: Cursor logs "
        "`Browser server skip reason … browser_features_disabled` while "
        "MCP status is still `connected` / toolCount=16. "
        "getAvailableTools skips the server, so CallMcpTool says "
        "`MCP server does not exist`. Team admin API may still report "
        "browserFeatures=true — this is in-memory AutorunSettings "
        "(often stuck from boot loading / stale-cache failClosed). "
        "mcp.json cannot fix it. Soft-restarting extensionHost/mcp-process "
        "is not enough; need Developer: Reload Window (or full Cursor "
        "quit) so Jwn()/browserFeatures re-evaluates, then a NEW Agent chat."
    )

    report = {
        "verdict": "READY_ON_DISK" if disk_ok else "MISSING_ON_DISK",
        "this_project": this,
        "peers_with_browser": [p["project"] for p in peers_with_browser],
        "gaps": gaps,
        "fix_steps": [
            "1. Confirm Settings shows Connected to Browser Tab (not Unable to verify browser policy)",
            "2. Cmd-Shift-P → Developer: Reload Window (required to clear browser_features_disabled)",
            "3. After reload: Open Browser Tab once if needed",
            "4. Start a NEW Agent chat (this chat's MCP catalog stays frozen)",
            "5. Re-run preflight + GetMcpTools pattern browser — must list cursor-ide-browser",
        ],
        "note": (
            "Cursor Browser UI working (tabs, logins, history) does NOT imply "
            "agent MCP tools are registered. SuperDev Path 6 must see "
            "cursor-ide-browser in GetMcpTools before smoke/session capture. "
            "Do not add cursor-ide-browser to mcp.json."
        ),
    }

    if args.as_json or not args.pretty:
        json.dump(report, sys.stdout, indent=2)
        print()
    else:
        print(f"verdict: {report['verdict']}")
        print(f"project: {this.get('project')}  browser_dir={this.get('has_browser_dir')}  tools={this.get('tool_count')}")
        print(f"servers: {', '.join(this.get('servers') or [])}")
        print(f"peers_with_browser: {', '.join(report['peers_with_browser']) or '(none scanned)'}")
        print("gaps:")
        for g in gaps:
            print(f"  - {g}")
        print("fix:")
        for s in report["fix_steps"]:
            print(f"  {s}")
        print(f"note: {report['note']}")
    return 0 if disk_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
