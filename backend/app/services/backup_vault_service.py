import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Tuple

from app.config import settings


def _build_rclone_env() -> dict:
    env = os.environ.copy()
    env.pop("RCLONE_BACKUP_DIR", None)
    return env


def _ensure_rclone_config() -> Path:
    config_path = Path(settings.RCLONE_CONFIG)
    seed_path = Path(settings.RCLONE_CONFIG_SEED)
    if seed_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(seed_path, config_path)
        except Exception:
            pass
    return config_path


def _vault_remote_dir() -> str:
    vault_dir = settings.RCLONE_VAULT_DIR
    remote = settings.RCLONE_REMOTE
    return f"{remote}:{vault_dir}" if vault_dir else f"{remote}:"


async def _run_rclone(args: List[str]) -> Tuple[bytes, bytes, int]:
    config_path = _ensure_rclone_config()
    env = _build_rclone_env()

    process = await asyncio.create_subprocess_exec(
        "rclone",
        *args,
        "--config",
        str(config_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    stdout, stderr = await process.communicate()
    return stdout or b"", stderr or b"", process.returncode


async def ensure_vault_dir() -> None:
    destination = _vault_remote_dir()
    await _run_rclone(["mkdir", destination])


async def list_vault_documents() -> List[Dict[str, Any]]:
    await ensure_vault_dir()
    destination = _vault_remote_dir()
    stdout, stderr, returncode = await _run_rclone(["lsjson", "--max-depth", "1", destination])
    if returncode != 0:
        raise RuntimeError(stderr.decode().strip() or "Failed to list backup documents")

    try:
        entries = json.loads(stdout.decode() or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError("Failed to parse backup document listing") from exc

    files = []
    for entry in entries or []:
        if entry.get("IsDir"):
            continue
        name = entry.get("Name") or ""
        if not name:
            continue
        if "__" in name:
            _, original_name = name.split("__", 1)
        else:
            original_name = name

        files.append(
            {
                "stored_name": name,
                "file_name": original_name,
                "size": entry.get("Size") or 0,
                "uploaded_at": (entry.get("ModTime") or "").replace("Z", ""),
            }
        )

    files.sort(key=lambda item: item.get("uploaded_at") or "", reverse=True)
    return files


async def upload_vault_document(stored_name: str, content: bytes) -> None:
    await ensure_vault_dir()
    destination = _vault_remote_dir()
    remote_path = f"{destination}/{stored_name}"

    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(content)
        temp_path = temp_file.name

    try:
        stdout, stderr, returncode = await _run_rclone(["copyto", temp_path, remote_path])
        if returncode != 0:
            message = stderr.decode().strip() or stdout.decode().strip() or "Upload failed"
            raise RuntimeError(message)
    finally:
        try:
            Path(temp_path).unlink(missing_ok=True)
        except Exception:
            pass


async def download_vault_document(stored_name: str) -> bytes:
    destination = _vault_remote_dir()
    remote_path = f"{destination}/{stored_name}"
    stdout, stderr, returncode = await _run_rclone(["cat", remote_path])
    if returncode != 0:
        raise RuntimeError(stderr.decode().strip() or "Failed to download file")
    return stdout
