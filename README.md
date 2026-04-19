# VoiceFlow

[English](README_EN.md)

**本地语音输入助手** — 按住 F12 说话，松开后自动识别并粘贴到光标位置。

无需云端，无需切换应用，说完即出字。

---

## 特性

- **全局热键触发** — 按住 F12 录音，松开识别，不打断当前工作流
- **自动粘贴** — 识别结果直接插入当前光标位置
- **纯本机运行** — 音频不走外网，隐私安全
- **低延迟** — 录音到出字端到端 1-3 秒
- **可替换后端** — ASR 模型可通过配置切换
- **轻量常驻** — 空闲 CPU 接近 0%，内存占用 < 50MB

## 快速开始

### 1. 安装系统依赖

```bash
sudo apt install xclip xdotool libportaudio2
```

> 三个均为 apt 官方仓库常用工具，无后台服务，对系统无影响。

### 2. 启动 ASR 服务

需要本地 vLLM 服务（如 qwen3-asr）：

```bash
pip install "vllm[audio]"
python -m vllm.entrypoints.openai.api_server \
  --model /path/to/qwen3-asr-1.7B \
  --host 0.0.0.0 --port 8000
```

### 3. 安装与运行

```bash
uv venv
uv pip install -e ".[dev]"
.venv/bin/python main.py
```

按住 **F12** 开始录音，松开后自动识别并粘贴。`Ctrl+C` 退出。

## 使用方式

```
任意应用中聚焦输入框 → 按住 F12 → 说话 → 松开 F12 → 文字自动出现在光标处
```

## 配置

编辑 `config.yaml` 自定义所有参数：

```yaml
hotkey:
  combo: f12              # 快捷键，支持 F1-F12、字母键

audio:
  sample_rate: 16000      # 采样率
  max_record_seconds: 60  # 单次最长录音时间

asr:
  endpoint: http://127.0.0.1:8000           # vLLM 服务地址
  model: /path/to/qwen3-asr-1.7B            # 模型名称
  language: zh                              # 语言

paste:
  linux_paste_shortcut: ctrl+v   # 粘贴快捷键
  restore_clipboard: true         # 是否恢复原剪贴板内容

ux:
  start_beep: true    # 开始录音提示音
  end_beep: true      # 结束录音提示音
  notify: true        # 桌面通知
```

## 项目结构

```
├── main.py              # 入口
├── state_machine.py     # 状态机（线程安全）
├── audio_recorder.py    # 录音模块
├── asr_client.py        # ASR HTTP 客户端
├── text_injector.py     # 剪贴板粘贴
├── hotkey_manager.py    # 全局热键（X11 XGrabKey）
├── notifier.py          # 桌面通知 & 提示音
├── utils.py             # 配置加载 & 日志
├── config.yaml          # 配置文件
├── pyproject.toml       # 依赖管理
├── tests/               # 单元测试（28 项）
└── scripts/             # 辅助脚本
```

## 技术栈

| 组件 | 技术 |
|------|------|
| 语言 | Python 3.13 |
| 包管理 | uv |
| 热键监听 | python-xlib（X11 XGrabKey） |
| 录音 | sounddevice |
| ASR 后端 | vLLM（OpenAI 兼容 API） |
| 剪贴板 | xclip + xdotool |
| 测试 | pytest + requests-mock |

## 运行测试

```bash
.venv/bin/python -m pytest tests/ -v
```

## 系统要求

- **OS**: Ubuntu 桌面（X11）
- **Python**: >= 3.10
- **GPU**: 需要运行 ASR 模型（如 RTX 4070 及以上）
- **ASR 模型**: vLLM 部署的语音识别模型

## 许可证

MIT
