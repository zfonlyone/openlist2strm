"""Weekly metadata/subtitle sync back to OpenList."""

import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, List

from app.config import get_config
from app.core.openlist import get_openlist_client

logger = logging.getLogger(__name__)

SYNC_EXTS = {".nfo", ".info", ".srt", ".ass", ".ssa", ".vtt", ".sub"}
STATE_FILE = Path("/data/weekly-sync-state.json")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_state() -> Dict[str, str]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: Dict[str, str]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _collect_local_candidates(base: Path) -> List[Path]:
    out: List[Path] = []
    if not base.exists():
        return out
    for p in base.rglob("*"):
        if p.is_file() and p.suffix.lower() in SYNC_EXTS:
            out.append(p)
    return out


async def run_weekly_sync() -> Dict[str, int]:
    """Sync local metadata/subtitle sidecars back to OpenList with diff-only strategy."""
    cfg = get_config()
    local_base = Path(cfg.paths.output)
    files = _collect_local_candidates(local_base)

    prev = _load_state()
    now_state: Dict[str, str] = {}

    client = get_openlist_client()

    uploaded = 0
    skipped = 0
    failed = 0

    # Default mirror root in OpenList (can be overridden by path_mapping key)
    mirror_root = cfg.path_mapping.get("__sync_target__", "/_emby_meta")

    for p in files:
        rel = p.relative_to(local_base).as_posix()
        digest = _sha256(p)
        now_state[rel] = digest

        if prev.get(rel) == digest:
            skipped += 1
            continue

        remote_path = f"{mirror_root.rstrip('/')}/{rel}"
        remote_dir = "/" + "/".join(remote_path.strip("/").split("/")[:-1])
        try:
            await client.mkdir(remote_dir)
        except Exception:
            # mkdir may fail when already exists; continue
            pass

        try:
            await client.upload_file(remote_path=remote_path, content=p.read_bytes(), as_task=True)
            uploaded += 1
        except Exception as e:
            failed += 1
            logger.warning(f"weekly sync upload failed {remote_path}: {e}")

    _save_state(now_state)
    logger.info(f"weekly sync done uploaded={uploaded} skipped={skipped} failed={failed}")
    return {"uploaded": uploaded, "skipped": skipped, "failed": failed}
