#!/usr/bin/env python3
"""Mirror selected workspace artifacts to Box with manifest + state tracking."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST_PATH = PROJECT_ROOT / "artifacts" / "devloop" / "box_workspace_manifest.json"
DEFAULT_STATE_PATH = PROJECT_ROOT / "data" / "system_state.json"

DEFAULT_INCLUDE_PATTERNS = [
    "artifacts/devloop/**/*.md",
    "artifacts/devloop/**/*.json",
    "artifacts/agentic_runs/**/*.md",
    "artifacts/agentic_runs/**/*.json",
    "docs/_reports/**/*.md",
    "data/system_state.json",
    "data/north_star_weekly_history.json",
    "data/market_signals/**/*.json",
    "wiki/Progress-Dashboard.md",
]

DEFAULT_EXCLUDE_PATTERNS = [
    "**/__pycache__/**",
    "**/*.tmp",
    "**/*.log",
    "**/node_modules/**",
]

BOX_API_BASE = "https://api.box.com/2.0"
BOX_UPLOAD_BASE = "https://upload.box.com/api/2.0"


@dataclass
class MirrorEntry:
    path: str
    size_bytes: int
    sha256: str
    modified_utc: str


def _safe_read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _safe_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _matches_any(path: str, patterns: list[str]) -> bool:
    p = Path(path)
    return any(p.match(pattern) for pattern in patterns)


def collect_workspace_files(
    *,
    repo_root: Path,
    include_patterns: list[str],
    exclude_patterns: list[str],
    max_file_bytes: int,
) -> list[Path]:
    selected: dict[str, Path] = {}
    for pattern in include_patterns:
        for candidate in repo_root.glob(pattern):
            if not candidate.is_file():
                continue
            rel = str(candidate.relative_to(repo_root))
            if _matches_any(rel, exclude_patterns):
                continue
            size_bytes = candidate.stat().st_size
            if max_file_bytes > 0 and size_bytes > max_file_bytes:
                continue
            selected[rel] = candidate
    return [selected[key] for key in sorted(selected)]


def build_manifest_entries(repo_root: Path, files: list[Path]) -> list[MirrorEntry]:
    entries: list[MirrorEntry] = []
    for path in files:
        stat = path.stat()
        entries.append(
            MirrorEntry(
                path=str(path.relative_to(repo_root)),
                size_bytes=int(stat.st_size),
                sha256=file_sha256(path),
                modified_utc=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            )
        )
    return entries


class BoxClient:
    """Minimal Box API client for folder/file mirroring."""

    def __init__(self, *, access_token: str, timeout_seconds: float) -> None:
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {access_token}"})
        self.timeout_seconds = timeout_seconds

    def list_items(self, folder_id: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        offset = 0
        limit = 1000
        while True:
            response = self.session.get(
                f"{BOX_API_BASE}/folders/{folder_id}/items",
                params={"limit": limit, "offset": offset, "fields": "id,name,type"},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            chunk = payload.get("entries", [])
            if isinstance(chunk, list):
                items.extend([row for row in chunk if isinstance(row, dict)])
            total_count = int(payload.get("total_count", len(items)))
            offset += limit
            if offset >= total_count:
                break
        return items

    def ensure_folder(self, *, parent_id: str, name: str) -> str:
        for item in self.list_items(parent_id):
            if item.get("type") == "folder" and item.get("name") == name:
                return str(item.get("id"))
        response = self.session.post(
            f"{BOX_API_BASE}/folders",
            json={"name": name, "parent": {"id": parent_id}},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return str(response.json()["id"])

    def ensure_folder_path(self, *, root_id: str, parts: list[str]) -> str:
        folder_id = root_id
        for part in parts:
            folder_id = self.ensure_folder(parent_id=folder_id, name=part)
        return folder_id

    def upload_or_update_file(self, *, folder_id: str, local_path: Path, remote_name: str) -> str:
        existing_file_id: str | None = None
        for item in self.list_items(folder_id):
            if item.get("type") == "file" and item.get("name") == remote_name:
                existing_file_id = str(item.get("id"))
                break

        with local_path.open("rb") as handle:
            if existing_file_id:
                response = self.session.post(
                    f"{BOX_UPLOAD_BASE}/files/{existing_file_id}/content",
                    files={
                        "attributes": (None, json.dumps({"name": remote_name})),
                        "file": (remote_name, handle),
                    },
                    timeout=self.timeout_seconds,
                )
            else:
                response = self.session.post(
                    f"{BOX_UPLOAD_BASE}/files/content",
                    files={
                        "attributes": (
                            None,
                            json.dumps({"name": remote_name, "parent": {"id": folder_id}}),
                        ),
                        "file": (remote_name, handle),
                    },
                    timeout=self.timeout_seconds,
                )
        response.raise_for_status()
        entries = response.json().get("entries", [])
        if not entries:
            return existing_file_id or ""
        return str(entries[0].get("id", existing_file_id or ""))


def sync_manifest_to_box(
    *,
    repo_root: Path,
    entries: list[MirrorEntry],
    access_token: str,
    root_folder_id: str,
    namespace: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    client = BoxClient(access_token=access_token, timeout_seconds=timeout_seconds)
    namespace_folder_id = client.ensure_folder(parent_id=root_folder_id, name=namespace)

    uploaded = 0
    updated = 0
    errors: list[str] = []

    for entry in entries:
        rel_path = Path(entry.path)
        folder_parts = list(rel_path.parent.parts) if rel_path.parent != Path(".") else []
        remote_folder_id = client.ensure_folder_path(
            root_id=namespace_folder_id, parts=folder_parts
        )
        local_path = repo_root / rel_path
        try:
            existed = False
            for item in client.list_items(remote_folder_id):
                if item.get("type") == "file" and item.get("name") == rel_path.name:
                    existed = True
                    break
            client.upload_or_update_file(
                folder_id=remote_folder_id,
                local_path=local_path,
                remote_name=rel_path.name,
            )
            if existed:
                updated += 1
            else:
                uploaded += 1
        except Exception as exc:  # noqa: BLE001 - keep sync resilient
            errors.append(f"{entry.path}: {exc}")

    return {
        "status": "ok" if not errors else "partial_failure",
        "uploaded_files": uploaded,
        "updated_files": updated,
        "error_count": len(errors),
        "errors": errors[:20],
        "namespace": namespace,
        "root_folder_id": root_folder_id,
    }


def _sync_state(state_path: Path, payload: dict[str, Any]) -> None:
    state = _safe_read_json(state_path)
    if not isinstance(state, dict):
        state = {}
    ops = state.get("ops", {})
    if not isinstance(ops, dict):
        ops = {}
    ops["box_workspace_mirror"] = payload
    state["ops"] = ops
    _safe_write_json(state_path, state)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate and sync Box workspace mirror manifest.")
    parser.add_argument("--repo-root", default=str(PROJECT_ROOT), help="Repository root path.")
    parser.add_argument(
        "--manifest-out", default=str(DEFAULT_MANIFEST_PATH), help="Manifest JSON output."
    )
    parser.add_argument("--state", default=str(DEFAULT_STATE_PATH), help="system_state.json path.")
    parser.add_argument(
        "--sync-state", action="store_true", help="Write run summary to system_state.ops."
    )
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help="Include glob pattern from repo root (repeatable).",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Exclude glob pattern from repo root (repeatable).",
    )
    parser.add_argument(
        "--max-file-bytes",
        type=int,
        default=5_000_000,
        help="Skip files larger than this size (default: 5MB).",
    )
    parser.add_argument(
        "--sync", action="store_true", help="Require Box sync (fails on missing creds)."
    )
    parser.add_argument(
        "--sync-if-credentials",
        action="store_true",
        help="Sync to Box only when credentials exist; otherwise manifest-only.",
    )
    parser.add_argument(
        "--box-access-token",
        default=os.getenv("BOX_ACCESS_TOKEN", ""),
        help="Box access token (defaults to BOX_ACCESS_TOKEN env).",
    )
    parser.add_argument(
        "--box-root-folder-id",
        default=os.getenv("BOX_ROOT_FOLDER_ID", ""),
        help="Box root folder id (defaults to BOX_ROOT_FOLDER_ID env).",
    )
    parser.add_argument(
        "--box-namespace",
        default=os.getenv("BOX_WORKSPACE_NAMESPACE", "trading-agent-workspace"),
        help="Top-level folder name used under root folder id.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=20.0,
        help="HTTP timeout for Box API calls.",
    )
    parser.add_argument("--print-json", action="store_true", help="Print manifest to stdout.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    manifest_path = Path(args.manifest_out).resolve()
    state_path = Path(args.state).resolve()

    include_patterns = args.include or list(DEFAULT_INCLUDE_PATTERNS)
    exclude_patterns = list(DEFAULT_EXCLUDE_PATTERNS) + list(args.exclude or [])
    files = collect_workspace_files(
        repo_root=repo_root,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        max_file_bytes=max(0, int(args.max_file_bytes)),
    )
    entries = build_manifest_entries(repo_root, files)

    total_bytes = sum(entry.size_bytes for entry in entries)
    sync_summary: dict[str, Any] = {
        "status": "manifest_only",
        "uploaded_files": 0,
        "updated_files": 0,
        "error_count": 0,
        "errors": [],
        "namespace": args.box_namespace,
    }

    token = str(args.box_access_token or "").strip()
    root_folder_id = str(args.box_root_folder_id or "").strip()
    creds_present = bool(token and root_folder_id)
    should_sync = bool(args.sync) or (bool(args.sync_if_credentials) and creds_present)

    if should_sync and not creds_present:
        if args.sync:
            print("error: --sync requires BOX_ACCESS_TOKEN and BOX_ROOT_FOLDER_ID", flush=True)
            return 1
        sync_summary["status"] = "skipped_missing_credentials"
    elif should_sync and creds_present:
        try:
            sync_summary = sync_manifest_to_box(
                repo_root=repo_root,
                entries=entries,
                access_token=token,
                root_folder_id=root_folder_id,
                namespace=args.box_namespace,
                timeout_seconds=float(args.timeout_seconds),
            )
        except Exception as exc:  # noqa: BLE001 - mirror failures should be observable
            sync_summary = {
                "status": "sync_failed",
                "uploaded_files": 0,
                "updated_files": 0,
                "error_count": 1,
                "errors": [str(exc)],
                "namespace": args.box_namespace,
                "root_folder_id": root_folder_id,
            }
            if args.sync:
                payload = {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "repo_root": str(repo_root),
                    "include_patterns": include_patterns,
                    "exclude_patterns": exclude_patterns,
                    "file_count": len(entries),
                    "total_bytes": total_bytes,
                    "entries": [entry.__dict__ for entry in entries],
                    "sync": sync_summary,
                }
                _safe_write_json(manifest_path, payload)
                if args.sync_state:
                    _sync_state(state_path, payload)
                print(f"error: box mirror sync failed -> {exc}")
                return 1

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo_root),
        "include_patterns": include_patterns,
        "exclude_patterns": exclude_patterns,
        "file_count": len(entries),
        "total_bytes": total_bytes,
        "entries": [entry.__dict__ for entry in entries],
        "sync": sync_summary,
    }

    _safe_write_json(manifest_path, payload)
    if args.sync_state:
        _sync_state(state_path, payload)

    print(
        "ok: box workspace mirror manifest updated",
        f"files={len(entries)}",
        f"sync_status={sync_summary.get('status')}",
        f"out={manifest_path}",
    )
    if args.print_json:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
