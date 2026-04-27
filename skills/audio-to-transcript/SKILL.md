---
name: audio-to-transcript
description: 音频文件（mp3/m4a/wav/aac/flac/ogg）→ 可读的 Markdown 文字稿。自动完成语音转写 + 说话人分离（阿里云 DashScope paraformer-v2）。最少交互：用户可以选择给每个 SPEAKER_XX 起名字，也可以直接跳过用原始标签。**保留原文不做内容整理、不做错字修正、不做解读**——只做简单排版让你方便阅读。每次运行落到 `~/Downloads/audio-to-transcript/<时间戳>_<音频名>/transcript.md`。
  当用户说"帮我把这个音频/录音转成文字稿"、"转写一下这个 mp3/m4a"、"这个录音转文字"、"这个音频转逐字稿"、"帮我把这段录音转成可读文字"、"把这个音频转成 markdown 文字稿"等，或者用户丢一个音频文件并提到转写/文字稿/逐字稿/转文字，立即使用此 skill。
  **不要用于**：①用户说"整理成公众号文章"、"发公众号的稿"、"出一篇稿子"——那是 audio-to-wechat-md 的任务；②视频文件——先让用户提取音频；③已经是文字稿的——直接给用户用。
---

# audio-to-transcript

音频转可读文字稿。**保留原文、零内容整理**。

## 找到 PLUGIN_ROOT

本 SKILL.md 位于 `<PLUGIN_ROOT>/skills/audio-to-transcript/SKILL.md`。**Plugin root = 本文件路径往上 2 层**。

下面命令里 `${PLUGIN_ROOT}` 是占位符，请替换成实际路径再运行。

## 前置检查

```
cd ${PLUGIN_ROOT} && .venv/bin/python skills/audio-to-transcript/scripts/run.py check
```

预期 `{"ok": true, ...}`。失败 → 指向 `${PLUGIN_ROOT}/README.md`。

## 工作流

### Step 1：预处理

```
cd ${PLUGIN_ROOT} && .venv/bin/python skills/audio-to-transcript/scripts/run.py preprocess <音频绝对路径>
```

stdout：`{"run_dir": "...", "wav": "...", "duration_sec": ...}`

时长检查：`>7200` 确认；`>43200` 拒绝。

### Step 2：上传 + 转写（慢）

```
cd ${PLUGIN_ROOT} && .venv/bin/python skills/audio-to-transcript/scripts/run.py transcribe <run_dir>
```

**后台跑**。stdout：`{"run_dir": "...", "raw_json": "...", "labeled_txt": "..."}`

### Step 3：说话人 Preview

```
cd ${PLUGIN_ROOT} && .venv/bin/python skills/audio-to-transcript/scripts/run.py preview <run_dir>
```

**warnings 非空**：原样给用户 + 三选项（继续 / 重跑 / 放弃）。

**正常**：

> 识别到 X 个说话人：
>
> **SPEAKER_00**（30 分 12 秒，123 句）
> - `[00:01:23]` "..."
>
> **要给他们起名字吗？**
> - 想起名：`SPEAKER_00=张三, SPEAKER_01=李四`
> - 不想起名：`跳过`

### Step 4：Finalize

**有名字**：
```
cd ${PLUGIN_ROOT} && .venv/bin/python skills/audio-to-transcript/scripts/run.py finalize <run_dir> SPEAKER_00=张三 SPEAKER_01=李四
```

**跳过**：
```
cd ${PLUGIN_ROOT} && .venv/bin/python skills/audio-to-transcript/scripts/run.py finalize <run_dir>
```

stdout：`{"run_dir": "...", "transcript": "...", "applied_mappings": {...}}`

### Step 5：交付

告诉用户：
1. 成品路径 `<run_dir>/transcript.md`
2. run_dir 清单（audio.wav / raw.json 等都在）
3. 打开方式 `open <run_dir>/transcript.md`

**不要做任何内容整理、改错字、提炼要点**——本 skill 承诺"保留原样、只简单排版"。

## 错误兜底

| 情况 | 怎么办 |
|---|---|
| `check` 失败 | 停，贴 errors |
| 音频不存在 | 确认路径 |
| ffmpeg / OSS / DashScope 失败 | 按 run.py 错误反馈 |
| 用户跳过后想加名字 | `finalize <run_dir> SPEAKER_00=xxx ...` 再跑一次即可 |

## 清理

```bash
rm -rf ~/Downloads/audio-to-transcript/<某次>
find ~/Downloads/audio-to-transcript -name "audio.wav" -delete
```
