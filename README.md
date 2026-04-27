# wechat-audio-toolkit

> 中文音频 → 公众号文章 / 可读文字稿。一个为 Claude Code / Cowork 写的 plugin。

## 这个 plugin 能做什么

| Skill | 输入 | 输出 |
|---|---|---|
| **`audio-to-wechat-md`** | 任何中文音频文件（mp3/m4a/wav/aac/flac/ogg）| 一篇 6000-10000 字的**公众号 Markdown 成品文章** + 5 个标题选项。会自动纠错、Q&A 重组、提炼金句。 |
| **`audio-to-transcript`** | 同上 | 一份**可读的 Markdown 文字稿**，保留原文不做任何整理。 |

底层用阿里云 **DashScope paraformer-v2** 做语音识别 + 说话人分离（diarization），**OSS** 做临时文件中转。

适用场景：访谈、播客、直播回放、会议录音、长视频音轨等长音频（最长 12 小时）。

---

## 一、装系统依赖

需要两样东西在你 Mac 上：

```bash
brew install ffmpeg uv
```

**ffmpeg** 用来做音频预处理（统一转成 16kHz mono wav）。**uv** 是 Python 的现代化环境管理工具，比 venv + pip 快十倍。

---

## 二、开通阿里云的两个服务

> 这一步**必须实名认证的阿里云账号**。如果你之前用过淘宝/支付宝，账号大概率已实名。

### 1. DashScope（语音识别）

1. 打开 https://bailian.console.aliyun.com/
2. 第一次会让你**开通百炼大模型服务**——免费开通，不扣钱
3. 在控制台搜索 `paraformer`，确认 `paraformer-v2` 模型显示"已开通"（一般会自动开）
4. 点头像 → "API-KEY 管理"（或访问 https://bailian.console.aliyun.com/?apiKey=1#/api-key）
5. 点"创建我的 API-KEY"
6. **立刻复制** `sk-` 开头的密钥（关闭弹窗后只能看到前后几位，找不回来就只能重建）

**计费**：约 ¥0.29/小时音频。新用户免费额度通常 36000 秒（10 小时），180 天有效。

### 2. OSS（临时文件中转）

paraformer 不接受本地文件，只接受公网 URL，所以需要 OSS 中转。

1. 打开 https://oss.console.aliyun.com/
2. 开通 OSS 服务（免费开通）
3. **创建 Bucket**：
   - 名字：自取，全阿里云唯一，建议 `audio-tools-<你的英文名>`
   - 地域：**华北 2（北京）**（和 DashScope 同地域，传输快）
   - 存储类型：**标准存储**
   - 读写权限：**私有**（脚本会生成带签名的临时 URL，不需要公开）
4. **创建 RAM 子账号**（强烈推荐，不要用主账号 AccessKey）：
   - 打开 https://ram.console.aliyun.com/users → 创建用户
   - 登录名：`audio-tools-bot`
   - 访问方式：**只勾"OpenAPI 调用访问"**
   - 创建后**立刻保存** AccessKey ID 和 Secret（同样只显示一次）
   - 给这个用户授权：进入用户详情 → 权限 → 新增授权 → 勾 `AliyunOSSFullAccess`

**计费**：几 MB 存储 + 几次上传下载 = 一个月几分钱。新用户有免费资源包。

---

## 三、配置环境变量

创建 `~/.claude/.env`：

```bash
# ~/.claude/.env

# DashScope（语音识别）
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxx

# OSS（文件中转）
OSS_ACCESS_KEY_ID=LTAI5txxxxxxxxxxx
OSS_ACCESS_KEY_SECRET=xxxxxxxxxxxxxxxxxxxx
OSS_BUCKET=audio-tools-yourname
OSS_ENDPOINT=oss-cn-beijing.aliyuncs.com
```

收紧权限（避免别的程序读到）：

```bash
chmod 600 ~/.claude/.env
```

---

## 四、安装 plugin

在 Claude Code（终端）里：

```
/plugin marketplace add anthropics/claude-plugins-community
/plugin install wechat-audio-toolkit
```

**或者手动安装**（适合改源码的开发者）：

```bash
git clone https://github.com/guoxiaowen/wechat-audio-toolkit ~/.claude/plugins/wechat-audio-toolkit
cd ~/.claude/plugins/wechat-audio-toolkit
uv venv && uv sync
```

然后告诉 Claude：
```
/plugin marketplace add ~/.claude/plugins/wechat-audio-toolkit
/plugin install wechat-audio-toolkit@local
```

---

## 五、装 Python 依赖

```bash
cd <plugin 安装目录>
uv venv
uv sync
```

---

## 六、自检

```bash
cd <plugin 安装目录>
.venv/bin/python skills/audio-to-wechat-md/scripts/run.py check
```

预期输出：

```json
{"ok": true, "plugin_root": "...", "output_root": "..."}
```

任何 error 都会清楚告诉你缺什么。

---

## 用法

### 出公众号文章

直接对 Claude 说：

> 帮我把这个音频 `/path/to/recording.mp3` 整理成公众号文章

Claude 会问你：
1. 发哪个公众号？(a) 自己的 / (b) 学习型 → 选 a 或 b
2. 转写完后，每个 SPEAKER_XX 是谁？

然后自动出文章 + 5 个标题。

### 只要可读文字稿

> 帮我把这个音频 `/path/to/recording.mp3` 转成文字稿

Claude 转完后会问你要不要给说话人起名字（可以选"跳过"）。

---

## 输出位置

每次运行独立目录，跨次不冲突：

```
~/Downloads/audio-to-wechat-md/<时间戳>_<音频名>/
├── manifest.json
├── audio.wav             # 预处理后的音频（~110MB/小时）
├── raw.json              # DashScope 原始结果
├── labeled.txt           # [SPEAKER_XX] 标签稿
├── final_transcript.md   # 替换真名后的逐字稿
└── article.md            # ← 公众号成品文章

~/Downloads/audio-to-transcript/<时间戳>_<音频名>/
├── manifest.json
├── audio.wav
├── raw.json
├── labeled.txt
└── transcript.md         # ← 可读文字稿
```

---

## 清理硬盘

`audio.wav` 大约 110MB/小时音频。长期累积会占空间。

```bash
# 列出所有历史
ls ~/Downloads/audio-to-wechat-md/
ls ~/Downloads/audio-to-transcript/

# 删某次
rm -rf ~/Downloads/audio-to-wechat-md/<某次>

# 只删 wav（保留文稿和成品）
find ~/Downloads/audio-to-wechat-md -name "audio.wav" -delete
find ~/Downloads/audio-to-transcript -name "audio.wav" -delete
```

---

## 常见问题

**Q: 阿里云的免费额度用完会怎样？**
A: 账户余额不够会停服。建议预存 ¥10-20 作缓冲，paraformer-v2 大约能跑 30+ 小时音频。

**Q: 我的录音音质很差，说话人分离不准怎么办？**
A: 重跑转写时加 `--speaker-count N` 强制指定人数（N = 你知道的实际人数）。

**Q: 超过 12 小时的音频怎么办？**
A: paraformer-v2 单任务上限就是 12h，超过的话需要自己用 ffmpeg 切段。

**Q: 视频文件能不能直接用？**
A: 不行。先用 ffmpeg 提音轨：
```bash
ffmpeg -i input.mp4 -vn -acodec copy output.m4a
```

**Q: 不在 Mac 上能用吗？**
A: Linux 应该能用（同样 brew/apt 装 ffmpeg + uv）。Windows 没测过，paths 可能要改。

**Q: 我的访谈在英文播客上，可以用吗？**
A: paraformer-v2 中英文都支持。对于纯英文长访谈，效果可能不如 OpenAI Whisper，但作者主要做中文场景，所以选了 paraformer。

---

## 隐私 & 安全

- 你的音频会**临时上传到自己的阿里云 OSS bucket**，转写完毕后**自动删除**
- DashScope 拿到的是 OSS 的临时签名 URL，1 小时后失效
- API key 永远只存在你自己机器的 `~/.claude/.env` 里，不会上传到任何地方
- 转写结果（raw.json / labeled.txt / 文稿等）只在你本地 `~/Downloads/` 下

---

## 反馈 / Issues

GitHub: https://github.com/guoxiaowen/wechat-audio-toolkit/issues

公众号：郭晓文（搜索关注，问题/反馈也可以从公众号过来）

---

## License

MIT。详见 [LICENSE](LICENSE)。

---

## 致谢

- [Anthropic](https://www.anthropic.com/) — Claude Code & Cowork
- 阿里云 [DashScope paraformer-v2](https://help.aliyun.com/zh/model-studio/paraformer-recorded-speech-recognition-restful-api) — 中文语音识别
- 阿里云 [OSS](https://www.aliyun.com/product/oss) — 文件存储
- [`anthropic-skills:transcript-to-wechat-md`](https://github.com/anthropics/claude-plugins-official) — 公众号文章 Q&A 整理逻辑（本 plugin 内有 snapshot 副本）
