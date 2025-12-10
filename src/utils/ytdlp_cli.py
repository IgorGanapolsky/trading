"""
Helper for running yt-dlp via the standalone CLI so we can avoid the Python
websockets dependency while still extracting metadata and downloading audio.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import urllib.request
from collections.abc import Iterable
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)
YT_DLP_VERSION = os.getenv("YTDLP_VERSION", "2025.10.14")
YT_DLP_CACHE_DIR = Path("tools/bin")
YT_DLP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
YT_DLP_BINARY = YT_DLP_CACHE_DIR / "yt-dlp"


def _download_ytdlp(destination: Path, version: str) -> None:
    """Download the yt-dlp standalone binary from the GitHub releases page."""
    url = f"https://github.com/yt-dlp/yt-dlp/releases/download/{version}/yt-dlp"
    LOGGER.info("Downloading yt-dlp %s to %s", version, destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url) as response:
            destination.write_bytes(response.read())
    except Exception as exc:
        raise RuntimeError(f"Failed to download yt-dlp from {url}: {exc}") from exc
    destination.chmod(0o755)


def ensure_ytdlp_binary() -> Path:
    """
    Locate the yt-dlp binary (PATH override, cached binary, or fresh download).

    Returns:
        Path to the executable that can be used from subprocess.
    """
    env_override = os.getenv("YTDLP_BINARY")
    if env_override:
        override_path = Path(env_override)
        if override_path.exists():
            LOGGER.debug("Using yt-dlp from YTDLP_BINARY=%s", override_path)
            return override_path
        LOGGER.warning("YT_DLP_BINARY=%s does not exist", override_path)

    system_binary = shutil.which("yt-dlp")
    if system_binary:
        LOGGER.debug("Using yt-dlp from PATH: %s", system_binary)
        return Path(system_binary)

    if YT_DLP_BINARY.exists():
        return YT_DLP_BINARY

    _download_ytdlp(YT_DLP_BINARY, YT_DLP_VERSION)
    return YT_DLP_BINARY


def run_ytdlp_dump_json(
    url: str,
    *,
    extract_flat: bool = False,
    playlistend: int | None = None,
    extra_args: Iterable[str] | None = None,
) -> Any:
    """
    Run yt-dlp with --dump-single-json so the caller receives the parsed metadata.
    """
    binary = ensure_ytdlp_binary()
    cmd = [
        str(binary),
        "--dump-single-json",
        "--no-warnings",
        "--quiet",
    ]

    if extract_flat:
        cmd.append("--flat-playlist")

    if playlistend is not None:
        cmd.extend(["--playlistend", str(playlistend)])

    if extra_args:
        cmd.extend(extra_args)

    cmd.append(url)
    process = subprocess.run(cmd, capture_output=True, text=True)

    if process.returncode != 0:
        message = process.stderr.strip() or process.stdout.strip()
        raise RuntimeError(f"yt-dlp metadata fetch failed: {message}")

    payload = process.stdout.strip()
    if not payload:
        raise RuntimeError("yt-dlp returned an empty JSON payload")

    return json.loads(payload)


def download_ytdlp_audio(
    video_url: str,
    output_path: Path,
    *,
    audio_format: str = "mp3",
    audio_quality: str = "192K",
    extra_args: Iterable[str] | None = None,
) -> None:
    """
    Use yt-dlp to download the best audio stream and convert it to the requested format.
    """
    binary = ensure_ytdlp_binary()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(binary),
        "--quiet",
        "--no-warnings",
        "-f",
        "bestaudio/best",
        "--extract-audio",
        "--audio-format",
        audio_format,
        "--audio-quality",
        audio_quality,
        "-o",
        str(output_path),
    ]

    if extra_args:
        cmd.extend(extra_args)

    cmd.append(video_url)
    process = subprocess.run(cmd, capture_output=True, text=True)

    if process.returncode != 0:
        message = process.stderr.strip() or process.stdout.strip()
        raise RuntimeError(f"yt-dlp audio download failed: {message}")
