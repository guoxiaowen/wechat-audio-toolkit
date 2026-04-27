---
name: audio-to-wechat-md
description: 音频文件（mp3/m4a/wav/aac/flac/ogg）→ 公众号 Markdown 成品文章。自动完成语音转写 + 说话人分离（阿里云 DashScope paraformer-v2），全程只问两个问题：①这个录音发到哪个公众号（你自己的访谈/学习型公众号）②每个 SPEAKER_XX 是谁。然后用 plugin 内打包的下游 skill（transcript-to-wechat-md 或 ai-interview-to-wechat-md）生成成品文章 + 5 个标题选项。每次运行的所有产物都落在 `~/Downloads/audio-to-wechat-md/<时间戳>_<音频名>/` 独立目录下，跨 session 不冲突。
  当用户说"帮我把这个音频/录音/mp3/m4a/wav 整理成公众号文章"、"这个访谈录音/播客帮我出一篇稿"、"这个语音文件/会议录音转公众号"、"这段录音整理成 markdown 发公众号"、"帮我把音频转写并整理成文章"、"把录音整理成稿子"等，或者用户直接丢一个音频文件并提到公众号/文章/整理/markdown/稿子，立即使用此 skill。
  不要用于：①用户只要转写文字稿、没提公众号/文章——用单独的转写工具（audio-to-transcript）即可；②视频文件——先让用户用 ffmpeg 提取音频；③已经是文字稿的内容——直接用 transcript-to-wechat-md 或 ai-interview-to-wechat-md。
---

# audio-to-wechat-md

把音频文件自动转成公众号文章。

## 找到 PLUGIN_ROOT

本 SKILL.md 位于 `<PLUGIN_ROOT>/skills/audio-to-wechat-md/SKILL.md`。**Plugin root = 本文件路径往上 2 层**。

下面命令里 `${PLUGIN_ROOT}` 是占位符，请替换成实际路径再运行。如果 shell 里 `CLAUDE_PLUGIN_ROOT` 环境变量已设置，可直接 `$CLAUDE_PLUGIN_ROOT`。

## 前置检查

```
cd ${PLUGIN_ROOT} && .venv/bin/python skills/audio-to-wechat-md/scripts/run.py check
```

预期 `{"ok": true, "plugin_root": "...", "output_root": "..."}`。失败时 errors 原样贴给用户，指向 `${PLUGIN_ROOT}/README.md` 的 setup 章节。

## 工作流

### Step 0：问用户发哪个公众号

> "这个录音是：
>   (a) 你自己的直播/访谈 → 用 `transcript-to-wechat-md`（适合：嘉宾访谈、个人分享、电商/小红书/创业实战录音）
>   (b) 你学习的别人的访谈 / AI 科技类 → 用 `ai-interview-to-wechat-md`（适合：学习型内容、AI/科技播客、英文访谈中文化）
> 选 a 还是 b？"

### Step 1：预处理

```
cd ${PLUGIN_ROOT} && .venv/bin/python skills/audio-to-wechat-md/scripts/run.py preprocess <音频绝对路径>
```

stdout：`{"run_dir": "...", "wav": "...", "duration_sec": ...}`

时长检查：`>7200`（2h）确认；`>43200`（12h）拒绝。

### Step 2：上传 + 转写（慢）

```
cd ${PLUGIN_ROOT} && .venv/bin/python skills/audio-to-wechat-md/scripts/run.py transcribe <run_dir>
```

**必须后台跑**（`run_in_background: true`）。stdout：`{"run_dir": "...", "raw_json": "...", "labeled_txt": "..."}`

### Step 3：说话人 Preview

```
cd ${PLUGIN_ROOT} && .venv/bin/python skills/audio-to-wechat-md/scripts/run.py preview <run_dir>
```

**warnings 非空**：原样给用户 + 三选项（继续 / `transcribe --speaker-count N` 重跑 / 放弃）。

**正常**：

> 识别到 X 个说话人：
>
> **SPEAKER_00**（30 分 12 秒，123 句）
> - `[00:01:23]` "..."
>
> 请告诉我每个人是谁：`SPEAKER_00=张三, SPEAKER_01=李四`

### Step 4：替换真名

```
cd ${PLUGIN_ROOT} && .venv/bin/python skills/audio-to-wechat-md/scripts/run.py rename <run_dir> SPEAKER_00=张三 SPEAKER_01=李四
```

### Step 5：生成文章（用 plugin 自带的下游 skill 指令）

**不要用 Skill 工具**调用 `anthropic-skills:*`——它们在 CLI 不存在。本 plugin 已自带本地副本：

1. Read `<run_dir>/final_transcript.md`
2. 根据 Step 0 选择，Read：
   - (a) → `${PLUGIN_ROOT}/article_skills/transcript-to-wechat-md/SKILL.md`
   - (b) → `${PLUGIN_ROOT}/article_skills/ai-interview-to-wechat-md/SKILL.md`
3. 同时 Read 它的 `references/example.md` 对齐质量
4. **严格按那份 SKILL.md 指令**生成公众号文章 + 5 个标题（不省略章节、不压缩、6000-10000 字）
5. 用 Write 工具写到 `<run_dir>/article.md`
6. 告诉用户成品路径 + run_dir 清单

## 错误兜底

| 情况 | 怎么办 |
|---|---|
| `check` 失败 | 停，贴 errors，指向 `${PLUGIN_ROOT}/README.md` |
| 音频不存在 | 确认路径 |
| ffmpeg / OSS / DashScope 失败 | 按 run.py 错误反馈 |
| 轮询超时（>1h）| 给 task_id |
| 说话人分离异常 | Step 3 warnings 处理 |

## 清理

```bash
rm -rf ~/Downloads/audio-to-wechat-md/<某次>
find ~/Downloads/audio-to-wechat-md -name "audio.wav" -delete
```
