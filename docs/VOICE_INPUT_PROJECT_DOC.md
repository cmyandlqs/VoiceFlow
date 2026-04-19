# 本地语音输入助手项目文档（Ubuntu + vLLM ASR）

- 版本: v0.1（MVP 设计文档）
- 日期: 2026-04-19
- 目标平台: Ubuntu 桌面（X11 优先，Wayland 兼容说明见后文）
- 核心交互: `按住说话` -> `松开结束` -> `直接粘贴到当前光标`
- 我的系统环境：ubuntu24：
    XDG_SESSION_TYPE=x11
    XDG_CURRENT_DESKTOP=ubuntu:GNOME

---

## 1. 背景与目标

### 1.1 背景
当前痛点是中文输入速度不足，键盘打字成为开发过程瓶颈。希望通过本地语音输入实现无感提效：

1. 不依赖云端，尽量本机推理。
2. 快捷键触发，不切换应用，不打断当前操作流。
3. 说完自动转文字并粘贴到焦点输入框。

### 1.2 项目目标
构建一个轻量常驻工具，满足以下能力：

1. 全局快捷键监听（按住触发）。
2. 录音采集与自动结束（松开即停，后续可扩展 VAD）。
3. 调用本机 ASR 服务（后端由 vLLM 部署，模型可替换）。
4. 文本自动注入当前输入框（直接粘贴）。
5. 低延迟、可观测、易维护。

### 1.3 非目标（MVP 阶段）

1. 不做复杂 GUI（只做托盘/日志即可）。
2. 不做多人会话、账号系统、远程同步。
3. 不追求一次性覆盖所有 Linux 桌面环境细节。

---

## 2. 用户体验定义（UX）

### 2.1 单次语音输入流程

1. 用户在任意应用聚焦输入框（IDE、浏览器、聊天窗口等）。
2. 按住快捷键（示例: `F12`）。
3. 工具开始录音，屏幕角落提示“正在聆听”。
4. 松开快捷键，立即停止录音并开始识别。
5. 识别结果返回后，自动粘贴到当前光标位置。
6. 可选提示音/气泡显示“已插入”。

### 2.2 体验指标（建议）

1. 快捷键触发延迟: < 50ms。
2. 停止录音到出字延迟: 500ms - 1500ms（取决于模型和 GPU）。
3. 单次失败率: < 2%（可重试）。

---

## 3. 系统架构

```text
+---------------------+
| Global Hotkey Layer |
+----------+----------+
           |
           v
+---------------------+       +-----------------------+
| Audio Capture Layer | ----> | ASR Client (HTTP/gRPC)|
| (16k mono WAV)      |       | -> vLLM ASR Service   |
+----------+----------+       +-----------+-----------+
           |                              |
           v                              v
+---------------------+       +-----------------------+
| State Controller    | <---- | Result Postprocess    |
| Idle/Recording/...  |       | punctuation/filter     |
+----------+----------+       +-----------+-----------+
           |
           v
+---------------------+
| Text Injector       |
| Clipboard+Paste     |
+---------------------+
```

### 3.1 设计原则

1. 分层解耦：录音、识别、粘贴彼此独立。
2. 可替换后端：ASR 接口抽象后可切换不同模型。
3. 失败可恢复：每个阶段失败都不崩溃，仅提示并回到 Idle。

---

## 4. 模块设计

## 4.1 `hotkey_manager`
职责：监听全局快捷键事件（按下/释放）。

输入：系统按键事件。
输出：`on_press`、`on_release` 回调。

建议实现：

1. Python: `pynput` / `keyboard`（X11 下通常可用）。
2. 若 Wayland 受限，提供降级策略（见 10.5）。

## 4.2 `audio_recorder`
职责：录制 PCM/WAV 音频。

建议参数：

1. 采样率 `16000`。
2. 通道 `1`（mono）。
3. 位深 `16-bit`。
4. 输出容器 `WAV`（兼容性最佳）。

建议库：`sounddevice` + `numpy` + `scipy.io.wavfile`（或 `pyaudio`）。

## 4.3 `asr_client`
职责：把录音发送到本地 ASR API，拿到文本。

输入：WAV 字节流或文件路径。
输出：识别文本、耗时、错误码。

约束：

1. 超时可配置（如 `timeout=20s`）。
2. 支持重试（如网络抖动 1 次重试）。
3. 错误分类明确（服务不可达/推理失败/空结果）。

## 4.4 `text_injector`
职责：把文本插入当前焦点输入框。

推荐策略（稳定优先）：

1. 保存当前剪贴板。
2. 写入识别文本到剪贴板。
3. 发送粘贴快捷键（Linux 常见 `Ctrl+Shift+V` 或 `Ctrl+V`）。
4. 恢复原剪贴板（可配置是否恢复）。

依赖建议：

1. `xclip` 或 `wl-clipboard`。
2. 键盘注入可用 `xdotool`（X11）或框架自带发送按键。

## 4.5 `app_state`
状态机：

1. `IDLE`
2. `RECORDING`
3. `TRANSCRIBING`
4. `PASTING`
5. `ERROR`

状态机价值：避免重复触发、竞态冲突（例如按键连击）。

## 4.6 `notifier`
职责：轻提示与日志。

1. 声音提示（开始/结束/失败）。
2. 桌面通知（`notify-send`）。
3. 控制台日志（后续可接文件轮转日志）。

---

## 5. ASR 接口协议（与 vLLM 服务对接）

说明：你后续会自行部署语音模型，本节定义“客户端约定”，避免前后端耦合。

### 5.1 推荐 REST 统一协议

- Endpoint: `POST /asr/transcribe`
- Content-Type: `multipart/form-data`
- 字段：
  - `audio_file`: WAV 文件
  - `language`: 可选（如 `zh`）
  - `task`: 可选（如 `transcribe`）
  - `prompt`: 可选（热词/上下文）

响应示例：

```json
{
  "text": "今天下午三点开会",
  "duration_ms": 742,
  "segments": [
    {"start": 0.00, "end": 1.24, "text": "今天下午"},
    {"start": 1.24, "end": 2.01, "text": "三点开会"}
  ],
  "request_id": "asr-20260419-001"
}
```

错误示例：

```json
{
  "error": {
    "code": "MODEL_BUSY",
    "message": "GPU queue is busy"
  }
}
```

### 5.2 兼容层建议

如你后续采用不同 ASR 服务形态（OpenAI-style API 或私有 API），客户端只改 `asr_client.py`，其余模块不动。

---

## 6. 配置设计

建议提供 `config.yaml`：

```yaml
hotkey:
  mode: hold_to_talk
  combo: f12

audio:
  sample_rate: 16000
  channels: 1
  dtype: int16
  max_record_seconds: 60

asr:
  endpoint: http://127.0.0.1:8001/asr/transcribe
  timeout_seconds: 20
  language: zh
  task: transcribe
  prompt: ""

paste:
  enabled: true
  method: clipboard
  linux_paste_shortcut: ctrl+shift+v
  restore_clipboard: true

ux:
  start_beep: true
  end_beep: true
  error_beep: true
  notify: true

log:
  level: INFO
  file: ./logs/voice_input.log
```

---

## 7. 目录结构建议

```text
voice_input/
  pyproject.toml
  config.yaml
  main.py
  hotkey_manager.py
  audio_recorder.py
  asr_client.py
  text_injector.py
  state_machine.py
  notifier.py
  utils.py
  tests/
    test_state_machine.py
    test_asr_client_mock.py
  scripts/
    run.sh
    check_audio.sh
```

如果希望与当前项目同仓库并存，可放到 `tools/voice_input/`。

---

## 8. 开发计划（里程碑）

## 8.1 Milestone 1: 跑通闭环（1 天）

1. 全局快捷键按住录音。
2. 松开停止并请求 ASR。
3. 返回文本后粘贴至光标。
4. 终端日志可见。

验收标准：连续 20 次操作无崩溃，成功率 >= 90%。

## 8.2 Milestone 2: 稳定性增强（1-2 天）

1. 状态机防抖与互斥。
2. 超时、重试与错误提示。
3. 剪贴板恢复机制。
4. 进程守护与自动重启（可选 systemd 用户服务）。

验收标准：异常情况下可自恢复，不影响正常键盘输入。

## 8.3 Milestone 3: 体验优化（持续）

1. VAD 自动截断。
2. 热词与术语增强。
3. 流式识别（边说边出字）。
4. 命令词（“换行”“删掉上一句”）。

---

## 9. 性能与资源估算

### 9.1 客户端资源

1. 常驻进程 CPU 占用低（空闲接近 0）。
2. 内存主要用于音频缓存（秒级，几十 MB 内）。

### 9.2 服务端资源（ASR 模型）

1. 显存占用随模型大小变化较大。
2. 建议先用中等模型验证体验，再切大模型。
3. 关键指标：实时因子（RTF）、首字延迟、吞吐并发。

---

## 10. 风险与解决策略

## 10.1 热键冲突

风险：系统或 IDE 已占用同组合键。

方案：

1. 提供配置改键。
2. 启动时检测并提示。

## 10.2 粘贴失败或粘贴到错误位置

风险：焦点切换导致文本进入错误窗口。

方案：

1. 识别完成后先做轻提示（可选）。
2. 支持 `dry_run`（仅复制不自动粘贴）用于排查。

## 10.3 ASR 服务不稳定

风险：超时、模型繁忙、崩溃。

方案：

1. 短重试 + 明确错误音。
2. 本地健康检查 `/health`。
3. 降级：失败时只复制原音频文件路径/留日志。

## 10.4 剪贴板污染

风险：覆盖用户原有剪贴板内容。

方案：

1. 默认启用“恢复原剪贴板”。
2. 对超大剪贴板可配置跳过恢复（性能换稳定）。

## 10.5 Wayland 兼容

风险：Wayland 对全局热键和模拟键盘限制更严格。

方案：

1. 优先支持 X11。
2. Wayland 下提供两种模式：
   - 通过桌面环境扩展/系统快捷键触发脚本。
   - 使用 clipboard-only（不主动发送粘贴按键，用户手动粘贴）。

---

## 11. 安全与隐私

1. 音频默认只走本机回环地址（`127.0.0.1`）。
2. 不上传外网，不记录原始音频（可配置临时文件自动删除）。
3. 日志脱敏，避免记录敏感业务内容。

---

## 12. 测试计划

## 12.1 功能测试

1. 按住说话/松开结束。
2. 快速短句、长句、停顿句。
3. 多应用粘贴（IDE、浏览器、IM）。

## 12.2 异常测试

1. ASR 服务关闭。
2. 网络超时（模拟）。
3. 麦克风不可用。
4. 无焦点输入框。

## 12.3 回归测试

1. 连续 30 分钟使用稳定性。
2. 高频触发下是否内存泄漏。
3. 剪贴板恢复正确率。

---

## 13. 运维与启动方式

### 13.1 环境准备与启动

```bash
# 安装 uv（如未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 创建虚拟环境并安装依赖
cd tools/voice_input
uv venv
uv pip install -r pyproject.toml

# 启动
uv run python main.py
```

### 13.2 用户级 systemd（建议）

可配置 `~/.config/systemd/user/voice-input.service`，实现登录后自动启动。

关键参数建议：

1. `Restart=always`
2. `RestartSec=2`
3. `Environment=DISPLAY=:0`（X11 时）

---

## 14. 观测指标（建议埋点）

1. `record_seconds`
2. `asr_latency_ms`
3. `end_to_end_latency_ms`
4. `asr_error_rate`
5. `paste_success_rate`

用于后续优化“是否真的比打字快”。

---

## 15. MVP 技术选型建议（Python）

使用 `uv` 管理虚拟环境与依赖。`pyproject.toml` 配置如下：

```toml
[project]
name = "voice-input"
version = "0.1.0"
description = "本地语音输入助手（Ubuntu + vLLM ASR）"
requires-python = ">=3.10"
dependencies = [
    "pynput==1.7.7",
    "sounddevice==0.5.1",
    "numpy==2.2.6",
    "requests==2.32.3",
    "pyperclip==1.9.0",
    "pyyaml==6.0.2",
]

[project.scripts]
voice-input = "main:main"
```

系统依赖建议：

```bash
sudo apt-get install -y xclip xdotool libportaudio2
```

注：如果你选择 `PyAudio` 路线，需安装 `portaudio19-dev` 等构建依赖。

---

## 16. 下一步实施建议

1. 先实现最小闭环（按住说话 -> 识别 -> 粘贴）。
2. 再做稳定性与兼容性（错误处理、剪贴板恢复、Wayland说明）。
3. 最后做体验增强（VAD、流式、命令词）。

推荐开发顺序：

1. `state_machine.py`
2. `audio_recorder.py`
3. `asr_client.py`
4. `text_injector.py`
5. `hotkey_manager.py`
6. `main.py` 组装

---

## 17. 附录：接口与事件约定（建议）

### 17.1 内部事件

1. `HOTKEY_PRESSED`
2. `HOTKEY_RELEASED`
3. `AUDIO_READY`
4. `ASR_SUCCESS`
5. `ASR_FAILED`
6. `PASTE_DONE`

### 17.2 错误码

1. `E_MIC_NOT_FOUND`
2. `E_AUDIO_CAPTURE_FAILED`
3. `E_ASR_TIMEOUT`
4. `E_ASR_UNAVAILABLE`
5. `E_PASTE_FAILED`

### 17.3 日志格式

```text
2026-04-19 14:03:21 INFO  [state] RECORDING -> TRANSCRIBING
2026-04-19 14:03:22 INFO  [asr] latency=812ms text_len=14
2026-04-19 14:03:22 INFO  [paste] success target=active_window
```

---

如果你认可这份文档，下一步可以直接开始创建 `voice_input/` 的可运行 MVP 代码骨架。
