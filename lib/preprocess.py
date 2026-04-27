"""Audio preprocessing: ffmpeg conversion + duration probing."""
import json
import shutil
import subprocess

_HOMEBREW_PATHS = ["/opt/homebrew/bin", "/usr/local/bin"]


def resolve_binary(name):
    """Find an executable by name. Checks PATH first, then Homebrew common paths.

    Raises FileNotFoundError with an install hint if not found.
    """
    found = shutil.which(name)
    if found:
        return found
    for d in _HOMEBREW_PATHS:
        candidate = f"{d}/{name}"
        if shutil.which(candidate):
            return candidate
    raise FileNotFoundError(
        f"{name} not found in PATH or {_HOMEBREW_PATHS}. Install: brew install ffmpeg"
    )


def to_16k_mono_wav(src, dst):
    """Convert any audio to 16kHz mono 16-bit PCM wav."""
    ffmpeg = resolve_binary("ffmpeg")
    cmd = [
        ffmpeg, "-y", "-loglevel", "error",
        "-i", src,
        "-ac", "1",
        "-ar", "16000",
        "-c:a", "pcm_s16le",
        dst,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{proc.stderr}")


def probe_duration(path):
    """Return audio duration in seconds (float)."""
    ffprobe = resolve_binary("ffprobe")
    cmd = [
        ffprobe, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed:\n{proc.stderr}")
    return float(json.loads(proc.stdout)["format"]["duration"])
