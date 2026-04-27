#!/usr/bin/env python3
"""Main dispatcher for audio-to-transcript skill (plugin version).

Each run gets its own directory under ~/Downloads/audio-to-transcript/<timestamp>_<audio-stem>/.

Subcommands:
    check                                   — verify env + deps
    preprocess <audio_path>                  — creates run dir, writes audio.wav
    transcribe <run_dir> [--speaker-count N] — OSS upload + paraformer-v2
    preview <run_dir>                        — per-speaker stats + samples
    finalize <run_dir> [SPEAKER_XX=name ...] — write transcript.md (mappings optional)
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN_ROOT / "lib"))

from dotenv import load_dotenv  # noqa: E402

OUTPUT_ROOT = Path.home() / "Downloads" / "audio-to-transcript"

load_dotenv(os.path.expanduser("~/.claude/.env"))


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def _safe_stem(name):
    stem = Path(name).stem
    return re.sub(r"[^\w\u4e00-\u9fff-]+", "-", stem).strip("-") or "untitled"


def _new_run_dir(audio_path):
    ts = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    stem = _safe_stem(audio_path)
    run_dir = OUTPUT_ROOT / f"{ts}_{stem}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def _require_run_dir(path):
    p = Path(path).expanduser().resolve()
    if not p.exists() or not p.is_dir():
        log(f"Error: run_dir does not exist or is not a directory: {p}")
        sys.exit(1)
    return p


def cmd_check():
    from preprocess import resolve_binary

    errors = []
    for bin_name in ("ffmpeg", "ffprobe"):
        try:
            resolve_binary(bin_name)
        except FileNotFoundError as e:
            errors.append(str(e))

    required_env = [
        "DASHSCOPE_API_KEY",
        "OSS_ACCESS_KEY_ID",
        "OSS_ACCESS_KEY_SECRET",
        "OSS_BUCKET",
        "OSS_ENDPOINT",
    ]
    for key in required_env:
        if not os.getenv(key):
            errors.append(f"Missing env var: {key}. Add it to ~/.claude/.env (see plugin README).")

    try:
        import dashscope  # noqa: F401
        import oss2  # noqa: F401
    except ImportError as e:
        errors.append(
            f"Python dep missing ({e}). Run: cd {PLUGIN_ROOT} && uv sync"
        )

    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        sys.exit(1)
    print(json.dumps({
        "ok": True,
        "plugin_root": str(PLUGIN_ROOT),
        "output_root": str(OUTPUT_ROOT),
    }))


def cmd_preprocess(audio_path):
    from preprocess import probe_duration, to_16k_mono_wav

    src = Path(audio_path).expanduser().resolve()
    if not src.exists():
        log(f"Error: audio file not found: {src}")
        sys.exit(1)

    run_dir = _new_run_dir(src.name)
    log(f"Created run directory: {run_dir}")

    wav_out = run_dir / "audio.wav"
    log(f"Converting {src.name} -> 16kHz mono wav...")
    to_16k_mono_wav(str(src), str(wav_out))
    dur = probe_duration(str(wav_out))
    log(f"Done. Duration: {dur:.1f}s ({dur/60:.1f} min).")

    manifest = {
        "source_audio": str(src),
        "source_name": src.name,
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        "duration_sec": dur,
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(json.dumps({
        "run_dir": str(run_dir),
        "wav": str(wav_out),
        "duration_sec": dur,
    }, ensure_ascii=False))


def cmd_transcribe(run_dir, speaker_count=None):
    from format_transcript import to_labeled_text
    from oss_upload import OSSClient
    from transcribe import download_result, poll, submit

    run_dir = _require_run_dir(run_dir)
    wav = run_dir / "audio.wav"
    if not wav.exists():
        log(f"Error: audio.wav not found in {run_dir}. Run preprocess first.")
        sys.exit(1)

    oss = OSSClient()
    object_key = f"audio-tools/{os.getpid()}_{run_dir.name}.wav"

    log(f"Uploading {wav.name} to OSS as {object_key}...")
    try:
        url = oss.upload_and_sign(str(wav), object_key, ttl=3600)
    except Exception as e:
        log(f"OSS upload failed: {e}")
        log("Check: (1) network, (2) OSS_ACCESS_KEY_*, (3) OSS_BUCKET exists and writable, (4) OSS_ENDPOINT region matches bucket.")
        sys.exit(1)

    try:
        log("Submitting transcription task (paraformer-v2, diarization enabled)...")
        task_id = submit(url, speaker_count=speaker_count)
        log(f"Task submitted: task_id={task_id}")
        log("Polling every 10s (max 1h)...")
        result_url = poll(task_id, timeout=3600, interval=10)
        log("Downloading result JSON...")
        raw = download_result(result_url)
    finally:
        log("Cleaning up OSS file...")
        try:
            oss.delete(object_key)
        except Exception as e:
            log(f"Warning: OSS cleanup failed (safe to ignore, URL expires in 1h): {e}")

    raw_path = run_dir / "raw.json"
    raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    labeled_path = run_dir / "labeled.txt"
    labeled_path.write_text(to_labeled_text(raw), encoding="utf-8")

    log(f"Wrote {raw_path.name} ({raw_path.stat().st_size} bytes) and {labeled_path.name}")
    print(json.dumps({
        "run_dir": str(run_dir),
        "raw_json": str(raw_path),
        "labeled_txt": str(labeled_path),
    }, ensure_ascii=False))


def cmd_preview(run_dir):
    from format_transcript import speaker_preview

    run_dir = _require_run_dir(run_dir)
    raw_path = run_dir / "raw.json"
    if not raw_path.exists():
        log(f"Error: raw.json not found in {run_dir}. Run transcribe first.")
        sys.exit(1)

    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    preview = speaker_preview(raw, samples_per_speaker=3)
    preview["run_dir"] = str(run_dir)
    print(json.dumps(preview, ensure_ascii=False, indent=2))


def cmd_finalize(run_dir, mappings):
    from format_transcript import to_readable_transcript

    run_dir = _require_run_dir(run_dir)
    raw_path = run_dir / "raw.json"
    manifest_path = run_dir / "manifest.json"
    if not raw_path.exists():
        log(f"Error: raw.json not found in {run_dir}. Run transcribe first.")
        sys.exit(1)
    if not manifest_path.exists():
        log(f"Error: manifest.json not found in {run_dir}.")
        sys.exit(1)

    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    speaker_mappings = {}
    for m in mappings or []:
        if "=" not in m:
            log(f"Bad mapping (need SPEAKER_XX=name): {m}")
            sys.exit(1)
        k, v = m.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not k or not v:
            log(f"Bad mapping (empty key or value): {m}")
            sys.exit(1)
        speaker_mappings[k] = v

    md = to_readable_transcript(
        raw=raw,
        audio_name=manifest.get("source_name", "未知音频"),
        source_path=manifest.get("source_audio", ""),
        duration_sec=manifest.get("duration_sec", 0),
        speaker_mappings=speaker_mappings,
    )

    out = run_dir / "transcript.md"
    out.write_text(md, encoding="utf-8")

    log(f"Wrote {out} ({out.stat().st_size} bytes)")
    print(json.dumps({
        "run_dir": str(run_dir),
        "transcript": str(out),
        "applied_mappings": speaker_mappings,
    }, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="audio-to-transcript dispatcher")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check")

    p_pre = sub.add_parser("preprocess")
    p_pre.add_argument("audio_path")

    p_tr = sub.add_parser("transcribe")
    p_tr.add_argument("run_dir")
    p_tr.add_argument("--speaker-count", type=int, default=None,
                      help="Force specific speaker count (default: auto)")

    p_pv = sub.add_parser("preview")
    p_pv.add_argument("run_dir")

    p_fi = sub.add_parser("finalize")
    p_fi.add_argument("run_dir")
    p_fi.add_argument("mappings", nargs="*",
                      help="Optional SPEAKER_XX=name pairs. Omit to keep SPEAKER_XX tags.")

    args = parser.parse_args()

    if args.cmd == "check":
        cmd_check()
    elif args.cmd == "preprocess":
        cmd_preprocess(args.audio_path)
    elif args.cmd == "transcribe":
        cmd_transcribe(args.run_dir, speaker_count=args.speaker_count)
    elif args.cmd == "preview":
        cmd_preview(args.run_dir)
    elif args.cmd == "finalize":
        cmd_finalize(args.run_dir, args.mappings)


if __name__ == "__main__":
    main()
