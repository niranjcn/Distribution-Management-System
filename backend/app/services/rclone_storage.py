import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from typing import List, Tuple

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

async def _run_rclone(args: List[str], timeout: int = 120) -> Tuple[bytes, bytes, int]:
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

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        process.kill()
        raise RuntimeError(f"rclone timed out after {timeout}s")

    return stdout or b"", stderr or b"", process.returncode

async def upload_file_to_rclone(folder: str, file_name: str, content: bytes) -> None:
    """Uploads a file to a specific folder on the configured rclone remote."""
    remote = settings.RCLONE_REMOTE
    destination = f"{remote}:{folder}"
    
    # Ensure directory exists (mkdir doesn't hurt if it already exists)
    await _run_rclone(["mkdir", destination])
    
    remote_path = f"{destination}/{file_name}"

    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(content)
        temp_path = temp_file.name

    try:
        stdout, stderr, returncode = await _run_rclone(["copyto", temp_path, remote_path])
        if returncode != 0:
            message = stderr.decode().strip() or stdout.decode().strip() or "Upload to Google Drive failed"
            raise RuntimeError(f"Rclone upload failed: {message}")
    finally:
        try:
            Path(temp_path).unlink(missing_ok=True)
        except Exception:
            pass

async def get_rclone_file_content(folder: str, file_name: str) -> bytes:
    """Fetches the bytes content of a file from the configured rclone remote."""
    remote = settings.RCLONE_REMOTE
    remote_path = f"{remote}:{folder}/{file_name}"
    
    stdout, stderr, returncode = await _run_rclone(["cat", remote_path])
    if returncode != 0:
        raise RuntimeError("File not found on Google Drive")
    return stdout
