"""DashScope paraformer-v2 async transcription with diarization."""
import json as jsonlib
import os
import sys
import time
import urllib.request

import dashscope
from dashscope.audio.asr import Transcription

dashscope.api_key = os.environ["DASHSCOPE_API_KEY"]


def _log(msg):
    print(msg, file=sys.stderr, flush=True)


def submit(file_url, speaker_count=None):
    """Submit async transcription task, return task_id."""
    kwargs = {
        "model": "paraformer-v2",
        "file_urls": [file_url],
        "language_hints": ["zh", "en"],
        "diarization_enabled": True,
    }
    if speaker_count is not None:
        kwargs["speaker_count"] = int(speaker_count)

    resp = Transcription.async_call(**kwargs)
    if resp.status_code != 200:
        raise RuntimeError(
            f"async_call failed: status={resp.status_code} code={resp.code} message={resp.message}"
        )
    return resp.output.task_id


def poll(task_id, timeout=3600, interval=10):
    """Poll until task reaches terminal state. Return the transcription_url."""
    start = time.time()
    last_status = None
    while True:
        resp = Transcription.fetch(task=task_id)
        if resp.status_code != 200:
            raise RuntimeError(
                f"fetch failed: status={resp.status_code} code={resp.code} message={resp.message}"
            )
        status = resp.output.task_status

        if status == "SUCCEEDED":
            results = resp.output.results or []
            if not results:
                raise RuntimeError(f"Task SUCCEEDED but results is empty: {resp.output}")
            r0 = results[0]
            sub_status = r0.get("subtask_status")
            if sub_status != "SUCCEEDED":
                raise RuntimeError(
                    f"Subtask not SUCCEEDED: subtask_status={sub_status}, detail={jsonlib.dumps(r0, ensure_ascii=False)}"
                )
            tr_url = r0.get("transcription_url")
            if not tr_url:
                raise RuntimeError(f"No transcription_url in result: {r0}")
            return tr_url

        if status == "FAILED":
            raise RuntimeError(
                f"Task FAILED: task_id={task_id}, output={jsonlib.dumps(dict(resp.output), ensure_ascii=False, default=str)}"
            )

        elapsed = int(time.time() - start)
        if elapsed > timeout:
            raise TimeoutError(
                f"Polling timeout after {timeout}s (task_id={task_id}, last_status={status}). "
                f"Task may still complete later — check https://dashscope.console.aliyun.com"
            )

        if status != last_status:
            _log(f"  status -> {status} (elapsed {elapsed}s)")
            last_status = status
        else:
            _log(f"  polling... status={status} elapsed={elapsed}s")

        time.sleep(interval)


def download_result(url):
    """GET the transcription_url and parse JSON."""
    req = urllib.request.Request(url, headers={"User-Agent": "audio-to-wechat-md/0.1"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    return jsonlib.loads(data.decode("utf-8"))
