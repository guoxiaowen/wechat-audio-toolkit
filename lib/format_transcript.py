"""Convert DashScope paraformer-v2 JSON to labeled text and speaker previews.

Input JSON shape (relevant parts):
{
  "transcripts": [
    {
      "channel_id": 0,
      "text": "full plain text",
      "sentences": [
        {"begin_time": 0, "end_time": 1234, "text": "...", "speaker_id": 0},
        ...
      ]
    }
  ]
}
"""
import datetime
from collections import defaultdict


def _sentences(raw):
    for tr in raw.get("transcripts", []) or []:
        for s in tr.get("sentences", []) or []:
            yield s


def _format_ts(ms):
    if ms is None:
        return "00:00"
    total_sec = int(int(ms) / 1000)
    h, rem = divmod(total_sec, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


def _speaker_tag(s):
    sid = s.get("speaker_id")
    if sid is None:
        sid = 0
    return f"SPEAKER_{int(sid):02d}"


def to_labeled_text(raw):
    """Turn JSON into a transcript with [SPEAKER_XX] tags and timestamps.

    Adjacent sentences from the same speaker are merged into one paragraph.
    """
    paragraphs = []
    current_speaker = None
    current_chunks = []
    current_start = None

    for s in _sentences(raw):
        spk = _speaker_tag(s)
        txt = (s.get("text") or "").strip()
        begin = s.get("begin_time", 0)
        if not txt:
            continue
        if spk != current_speaker:
            if current_chunks:
                paragraphs.append(
                    f"[{current_speaker}] [{_format_ts(current_start)}] {''.join(current_chunks)}"
                )
            current_speaker = spk
            current_chunks = []
            current_start = begin
        current_chunks.append(txt)

    if current_chunks:
        paragraphs.append(
            f"[{current_speaker}] [{_format_ts(current_start)}] {''.join(current_chunks)}"
        )

    return "\n\n".join(paragraphs)


def speaker_preview(raw, samples_per_speaker=3):
    """Per-speaker stats + representative sample sentences + warning heuristics."""
    by_speaker = defaultdict(list)
    for s in _sentences(raw):
        by_speaker[_speaker_tag(s)].append(s)

    speakers = []
    for spk, sents in sorted(by_speaker.items()):
        total_ms = sum(
            max(0, (s.get("end_time") or 0) - (s.get("begin_time") or 0)) for s in sents
        )
        # Prefer medium-length sentences (10-120 chars), sorted by length desc
        candidates = [s for s in sents if (s.get("text") or "").strip()]
        medium = sorted(
            [s for s in candidates if 10 <= len((s.get("text") or "").strip()) <= 120],
            key=lambda x: len((x.get("text") or "").strip()),
            reverse=True,
        )
        samples = []
        seen = set()

        def _add(s):
            t = (s.get("text") or "").strip()
            if not t or t in seen:
                return False
            samples.append({"time": _format_ts(s.get("begin_time", 0)), "text": t})
            seen.add(t)
            return True

        for s in medium:
            if len(samples) >= samples_per_speaker:
                break
            _add(s)
        if len(samples) < samples_per_speaker:
            fallback = sorted(candidates, key=lambda x: len((x.get("text") or "").strip()), reverse=True)
            for s in fallback:
                if len(samples) >= samples_per_speaker:
                    break
                _add(s)

        speakers.append({
            "id": spk,
            "total_seconds": round(total_ms / 1000),
            "sentence_count": len(sents),
            "samples": samples,
        })

    warnings = []
    n = len(speakers)
    if n == 0:
        warnings.append("未识别出任何说话人——转写结果可能为空，建议检查原始音频。")
    elif n == 1:
        warnings.append(
            "只识别出 1 个说话人。如果实际是多人对话，说明分离失败（常见原因：音质差、说话人音色相近、说话重叠）。"
            "可以选择重跑转写时用 `--speaker-count N` 强制指定人数。"
        )
    if n > 6:
        warnings.append(
            f"识别出 {n} 个说话人，偏多。可能是背景杂音或同一人被切成多段。"
            "建议在认人阶段把无关的 SPEAKER 标成「忽略」。"
        )
    for spk in speakers:
        if spk["total_seconds"] < 10:
            warnings.append(
                f"{spk['id']} 总时长仅 {spk['total_seconds']}s（{spk['sentence_count']} 句），"
                "很可能是误识别（背景音、咳嗽、短促插话）。"
            )

    return {
        "speaker_count": n,
        "warnings": warnings,
        "speakers": speakers,
    }


def _human_duration(sec):
    """Turn 10376.6 -> '2 小时 52 分 56 秒'."""
    sec = int(sec or 0)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h} 小时")
    if m or h:
        parts.append(f"{m} 分")
    parts.append(f"{s} 秒")
    return " ".join(parts)


def to_readable_transcript(raw, audio_name, source_path, duration_sec, speaker_mappings=None):
    """Produce a minimally-edited, readable Markdown transcript.

    - Merges adjacent sentences from the same speaker into one paragraph
    - Each paragraph: **speaker name** `timestamp` \n\n content \n\n
    - If speaker_mappings provided, replaces SPEAKER_XX with the given name;
      otherwise keeps SPEAKER_XX tags.
    - No text cleanup, no error correction, no summarization.
    """
    speaker_mappings = speaker_mappings or {}

    # Count speakers
    speakers_seen = set()
    for s in _sentences(raw):
        speakers_seen.add(_speaker_tag(s))
    speaker_count = len(speakers_seen)

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # Header
    lines = [
        f"# 转写稿：{audio_name}",
        "",
        f"- **源音频**：`{source_path}`",
        f"- **时长**：{_human_duration(duration_sec)}",
        f"- **说话人数**：{speaker_count}",
        f"- **转写时间**：{now}",
        "",
        "---",
        "",
    ]

    # Body: merge consecutive same-speaker sentences into paragraphs
    current_speaker = None
    current_name = None
    current_chunks = []
    current_start = None

    def _flush():
        if current_chunks:
            lines.append(f"**{current_name}** `{_format_ts(current_start)}`")
            lines.append("")
            lines.append("".join(current_chunks))
            lines.append("")

    for s in _sentences(raw):
        spk = _speaker_tag(s)
        name = speaker_mappings.get(spk, spk)
        txt = (s.get("text") or "").strip()
        if not txt:
            continue
        begin = s.get("begin_time", 0)
        if spk != current_speaker:
            _flush()
            current_speaker = spk
            current_name = name
            current_chunks = []
            current_start = begin
        current_chunks.append(txt)

    _flush()

    return "\n".join(lines)
