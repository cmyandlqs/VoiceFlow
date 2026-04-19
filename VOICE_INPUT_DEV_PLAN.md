# 语音输入助手 - 开发计划文档

- 版本: v0.1
- 日期: 2026-04-19
- 基于设计文档: `VOICE_INPUT_PROJECT_DOC.md`

---

## 1. 开发环境搭建

### 1.1 前置条件

| 依赖 | 版本 | 安装方式 |
|------|------|----------|
| Python | >= 3.10 | 系统自带 |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| xclip | any | `sudo apt install xclip` |
| xdotool | any | `sudo apt install xdotool` |
| libportaudio2 | any | `sudo apt install libportaudio2` |
| vLLM ASR 服务 | 运行中 | 独立部署，监听 `http://127.0.0.1:8001` |

### 1.2 初始化步骤

```bash
cd /home/sikm/Project/AI-Project/TTS/voice_input
uv venv
uv pip install -r pyproject.toml
```

### 1.3 验证环境就绪

| 检查项 | 命令 | 预期结果 |
|--------|------|----------|
| Python 版本 | `uv run python --version` | >= 3.10 |
| pynput 可导入 | `uv run python -c "import pynput"` | 无报错 |
| sounddevice 可导入 | `uv run python -c "import sounddevice"` | 无报错 |
| xclip 可用 | `echo test \| xclip -sel clip` | 无报错 |
| xdotool 可用 | `xdotool getactivewindow` | 返回窗口 ID |
| ASR 服务可达 | `curl http://127.0.0.1:8001/health` | 200 OK |
| 麦克风可用 | `uv run python scripts/check_audio.sh` | 列出设备 |

### 1.4 环境就绪验收

- [ ] 所有检查项通过
- [ ] `uv run python main.py` 不报 import 错误

---

## 2. Milestone 1: 最小闭环（预计 1 天）

### 2.1 目标

按住 F12 录音 -> 松开识别 -> 文本粘贴到光标。终端日志可见全流程。

### 2.2 任务拆解

#### Task 1.1: state_machine.py

**描述**: 实现状态机，管理 IDLE / RECORDING / TRANSCRIBING / PASTING / ERROR 五个状态。

**实现要求**:

- 使用 enum 定义 `AppState`
- 使用 threading.Lock 防止并发状态变更
- 提供 `transition(new_state, event)` 方法，非法转换抛异常或记日志
- 提供 `is_idle` / `is_recording` 等便利属性
- 每次状态变更打印日志: `[时间] [state] OLD -> NEW`

**验收条件**:

- [ ] 合法状态转换正常工作: IDLE->RECORDING->TRANSCRIBING->PASTING->IDLE
- [ ] 非法状态转换被拒绝并记日志（如 IDLE 直接到 TRANSCRIBING）
- [ ] 线程安全：两个线程同时请求转换不会导致状态不一致
- [ ] ERROR 状态可以从任意非 IDLE 状态进入
- [ ] ERROR 状态可以转换回 IDLE

**测试用例**:

```python
def test_normal_flow():
    sm = StateMachine()
    assert sm.state == AppState.IDLE
    sm.transition(AppState.RECORDING, "HOTKEY_PRESSED")
    assert sm.state == AppState.RECORDING
    sm.transition(AppState.TRANSCRIBING, "HOTKEY_RELEASED")
    assert sm.state == AppState.TRANSCRIBING
    sm.transition(AppState.PASTING, "ASR_SUCCESS")
    assert sm.state == AppState.PASTING
    sm.transition(AppState.IDLE, "PASTE_DONE")
    assert sm.state == AppState.IDLE

def test_invalid_transition():
    sm = StateMachine()
    with pytest.raises(InvalidTransitionError):
        sm.transition(AppState.TRANSCRIBING, "INVALID")

def test_error_from_any_state():
    for state in [AppState.RECORDING, AppState.TRANSCRIBING, AppState.PASTING]:
        sm = StateMachine()
        sm.transition(state, "FORCE")
        sm.transition(AppState.ERROR, "SOME_ERROR")
        assert sm.state == AppState.ERROR
        sm.transition(AppState.IDLE, "RECOVERED")
        assert sm.state == AppState.IDLE

def test_thread_safety():
    sm = StateMachine()
    errors = []
    def try_transition():
        try:
            sm.transition(AppState.RECORDING, "HOTKEY_PRESSED")
        except Exception as e:
            errors.append(e)
    threads = [threading.Thread(target=try_transition) for _ in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert sm.state in [AppState.IDLE, AppState.RECORDING]
```

---

#### Task 1.2: audio_recorder.py

**描述**: 实现录音模块，按住时采集 16kHz mono 16-bit PCM，松开时输出 WAV 文件/字节流。

**实现要求**:

- 使用 `sounddevice` 进行录音
- 采样率 16000，通道 1，位深 int16
- 提供 `start()` / `stop()` 方法
- `stop()` 返回 `numpy.ndarray`（PCM 数据）和临时 WAV 文件路径
- 录音时打印采样状态到日志
- 录音时长上限 60 秒，超时自动停止

**验收条件**:

- [ ] `start()` 后 `sounddevice` 开始录音
- [ ] `stop()` 返回有效的 WAV 字节流
- [ ] 生成的 WAV 可以用 `ffprobe` 识别为 16kHz mono 16-bit
- [ ] 超过 60 秒自动停止录音
- [ ] 未 start 就 stop 不崩溃，返回空结果或抛明确异常
- [ ] 麦克风不可用时抛 `E_MIC_NOT_FOUND` 错误码

**测试用例**:

```python
def test_record_and_stop():
    recorder = AudioRecorder()
    recorder.start()
    time.sleep(1)
    data, wav_path = recorder.stop()
    assert data is not None
    assert len(data) > 0
    assert os.path.exists(wav_path)
    # 验证 WAV 格式
    rate, samples = wavfile.read(wav_path)
    assert rate == 16000
    assert samples.dtype == np.int16
    assert samples.ndim == 1

def test_max_duration():
    recorder = AudioRecorder(max_seconds=2)
    recorder.start()
    time.sleep(3)
    data, _ = recorder.stop()  # 应已在 2 秒时自动停止
    assert len(data) <= 16000 * 2.1  # 允许少量误差

def test_stop_without_start():
    recorder = AudioRecorder()
    with pytest.raises(RuntimeError):
        recorder.stop()
```

---

#### Task 1.3: asr_client.py

**描述**: HTTP 客户端，将 WAV 发送到本地 ASR 服务并返回识别文本。

**实现要求**:

- POST `multipart/form-data` 到 `{endpoint}/asr/transcribe`
- 超时可配置（默认 20s）
- 失败自动重试 1 次
- 错误分类: `E_ASR_TIMEOUT` / `E_ASR_UNAVAILABLE` / 空`E_ASR_EMPTY`
- 返回结构: `ASRResult(text, duration_ms, request_id)`

**验收条件**:

- [ ] ASR 服务正常时返回正确文本
- [ ] ASR 服务关闭时返回 `E_ASR_UNAVAILABLE`，不崩溃
- [ ] 超时时返回 `E_ASR_TIMEOUT`，不崩溃
- [ ] 空音频（静音）时返回 `E_ASR_EMPTY` 或空文本
- [ ] 重试机制生效（mock 模拟第一次失败第二次成功）

**测试用例**:

```python
def test_successful_transcription(requests_mock):
    requests_mock.post("http://127.0.0.1:8001/asr/transcribe",
        json={"text": "你好世界", "duration_ms": 500})
    client = ASRClient("http://127.0.0.1:8001")
    result = client.transcribe(b"fake_wav_bytes")
    assert result.text == "你好世界"
    assert result.duration_ms == 500

def test_service_unavailable(requests_mock):
    requests_mock.post("http://127.0.0.1:8001/asr/transcribe",
        status_code=503)
    client = ASRClient("http://127.0.0.1:8001", max_retries=1)
    with pytest.raises(ASRUnavailableError):
        client.transcribe(b"fake_wav_bytes")

def test_timeout(requests_mock):
    requests_mock.post("http://127.0.0.1:8001/asr/transcribe",
        exc=requests.exceptions.Timeout)
    client = ASRClient("http://127.0.0.1:8001", timeout=1, max_retries=0)
    with pytest.raises(ASRTimeoutError):
        client.transcribe(b"fake_wav_bytes")

def test_retry_success(requests_mock):
    requests_mock.post("http://127.0.0.1:8001/asr/transcribe",
        [{"status_code": 503}, {"json": {"text": "重试成功"}}])
    client = ASRClient("http://127.0.0.1:8001", max_retries=1)
    result = client.transcribe(b"fake_wav_bytes")
    assert result.text == "重试成功"
```

---

#### Task 1.4: text_injector.py

**描述**: 将识别文本粘贴到当前光标位置。

**实现要求**:

- 保存当前剪贴板内容
- 写入识别文本到剪贴板
- 发送 Ctrl+Shift+V（可配置）模拟粘贴
- 恢复原剪贴板内容
- 依赖 `xclip` 和 `xdotool`

**验收条件**:

- [ ] 文本成功粘贴到终端/IDE/浏览器输入框
- [ ] 原剪贴板内容在粘贴后恢复
- [ ] 无焦点窗口时不崩溃，记日志
- [ ] 空文本不触发粘贴

**测试用例**:

```python
def test_paste_text():
    injector = TextInjector()
    injector.inject("测试文本")
    # 手动验证: 粘贴到终端/gedit 后内容正确

def test_empty_text_no_paste():
    injector = TextInjector()
    injector.inject("")  # 不应崩溃，不应粘贴

def test_clipboard_restore():
    injector = TextInjector(restore_clipboard=True)
    subprocess.run(["xclip", "-sel", "clip"], input=b"原内容", check=True)
    injector.inject("新内容")
    time.sleep(0.5)
    result = subprocess.run(["xclip", "-sel", "clip", "-o"],
        capture_output=True, text=True)
    assert result.stdout == "原内容"
```

---

#### Task 1.5: hotkey_manager.py

**描述**: 监听全局 F12 按键事件（按下/释放）。

**实现要求**:

- 使用 `pynput` 监听全局键盘
- 快捷键可配置（默认 F12）
- 提供 `on_press` / `on_release` 回调注册
- 启动时打印 `Hotkey registered: F12`

**验收条件**:

- [ ] 按下 F12 触发 on_press 回调
- [ ] 松开 F12 触发 on_release 回调
- [ ] 其他按键不触发回调
- [ ] 长按 F12 不产生重复触发（debounce）

**测试用例**:

```python
def test_hotkey_press_release():
    pressed_events = []
    released_events = []
    mgr = HotkeyManager(combo="f12")
    mgr.on_press(lambda: pressed_events.append(1))
    mgr.on_release(lambda: released_events.append(1))
    mgr.start()
    time.sleep(0.5)
    # 模拟按键（需要实际按下 F12 或用 xdotool）
    subprocess.run(["xdotool", "key", "F12"])
    time.sleep(0.2)
    subprocess.run(["xdotool", "keyup", "F12"])
    time.sleep(0.2)
    mgr.stop()
    assert len(pressed_events) == 1
    assert len(released_events) == 1
```

---

#### Task 1.6: main.py 组装

**描述**: 将所有模块组装成完整的按住说话流程。

**实现要求**:

- 读取 `config.yaml`
- 初始化各模块并注册回调
- F12 按下 -> start recording
- F12 松开 -> stop recording -> ASR -> paste -> idle
- 打印全流程日志
- Ctrl+C 优雅退出

**验收条件**:

- [ ] `uv run python main.py` 启动后常驻
- [ ] 按住 F12 录音，松开后识别并粘贴
- [ ] 连续 20 次操作无崩溃
- [ ] Ctrl+C 正常退出，无僵尸进程
- [ ] 日志清晰记录每次状态变更

**集成测试**:

```
测试场景: 完整语音输入闭环
前置: ASR 服务运行中
步骤:
  1. 启动 main.py
  2. 按住 F12，说"今天天气不错"，松开
  3. 观察终端日志: IDLE -> RECORDING -> TRANSCRIBING -> PASTING -> IDLE
  4. 验证文本"今天天气不错"出现在当前光标位置
  5. 重复 20 次
预期: 成功率 >= 90% (18/20)
```

---

### Milestone 1 总验收

| 验收项 | 通过标准 |
|--------|----------|
| 单元测试 | `uv run pytest tests/` 全部通过 |
| 闭环流程 | 按住 F12 -> 说话 -> 松开 -> 文本粘贴到光标 |
| 连续稳定性 | 20 次操作成功率 >= 90% |
| 日志可读 | 每次操作有完整状态变更日志 |
| 异常不崩溃 | ASR 服务关闭时工具不崩溃，提示错误 |
| 优雅退出 | Ctrl+C 退出，无残留进程 |

---

## 3. Milestone 2: 稳定性增强（预计 1-2 天）

### 3.1 目标

在 Milestone 1 基础上增强错误处理、防抖、剪贴板恢复，达到日常可用水平。

### 3.2 任务拆解

#### Task 2.1: notifier.py 提示模块

**描述**: 实现声音提示和桌面通知。

**验收条件**:

- [ ] 开始录音时播放提示音
- [ ] 识别完成时播放提示音
- [ ] 识别失败时播放错误提示音
- [ ] `notify-send` 发送桌面通知
- [ ] 声音/通知可通过配置独立开关

**测试用例**:

```python
def test_notify_send():
    notifier = Notifier(notify_enabled=True, sound_enabled=False)
    notifier.notify("正在聆听...")  # 应出现桌面通知

def test_sound_play():
    notifier = Notifier(notify_enabled=False, sound_enabled=True)
    notifier.play_start_beep()  # 应听到声音
    notifier.play_end_beep()
    notifier.play_error_beep()
```

---

#### Task 2.2: 剪贴板恢复与异常防护

**描述**: 完善剪贴板恢复逻辑，处理大内容、二进制内容等边界场景。

**验收条件**:

- [ ] 正常文本剪贴板内容 100% 恢复
- [ ] 图片等二进制剪贴板内容不崩溃（跳过恢复并记日志）
- [ ] 剪贴板为空时正常工作
- [ ] 粘贴失败时记日志，不崩溃

**测试用例**:

```python
def test_restore_after_paste():
    injector = TextInjector(restore_clipboard=True)
    set_clipboard("重要内容ABC")
    injector.inject("语音输入文本")
    time.sleep(1)
    assert get_clipboard() == "重要内容ABC"

def test_empty_clipboard():
    clear_clipboard()
    injector = TextInjector(restore_clipboard=True)
    injector.inject("新文本")  # 不崩溃
    time.sleep(1)

def test_large_clipboard():
    large_text = "X" * 1_000_000
    set_clipboard(large_text)
    injector = TextInjector(restore_clipboard=True)
    injector.inject("短文本")
    time.sleep(1)
    assert get_clipboard() == large_text
```

---

#### Task 2.3: 进程守护（systemd 用户服务）

**描述**: 创建 systemd 用户服务，实现登录后自动启动、崩溃自动重启。

**实现要求**:

- 服务文件: `~/.config/systemd/user/voice-input.service`
- `Restart=always`, `RestartSec=2`
- 日志输出到 journalctl

**验收条件**:

- [ ] `systemctl --user start voice-input` 启动服务
- [ ] `systemctl --user status voice-input` 显示 active
- [ ] 手动 kill 进程后 2 秒内自动重启
- [ ] `systemctl --user stop voice-input` 停止服务

**测试用例**:

```
测试场景: 服务自动重启
步骤:
  1. systemctl --user start voice-input
  2. systemctl --user status voice-input  # 确认 active
  3. 获取 PID: pgrep -f main.py
  4. kill -9 <PID>
  5. sleep 3
  6. pgrep -f main.py  # 应返回新 PID
预期: 新 PID 出现，服务自动恢复
```

---

#### Task 2.4: 配置验证与热加载

**描述**: 启动时验证 config.yaml 合法性，运行时 SIGHUP 热加载配置。

**验收条件**:

- [ ] 缺少必要字段时启动报错并提示
- [ ] 非法值（如采样率非数字）时启动报错
- [ ] SIGHUP 后重新加载配置（可选）

**测试用例**:

```python
def test_missing_required_field():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml') as f:
        yaml.dump({"hotkey": {}}, f)
        f.flush()
        with pytest.raises(ConfigValidationError):
            load_config(f.name)

def test_invalid_sample_rate():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml') as f:
        yaml.dump({"audio": {"sample_rate": "abc"}}, f)
        f.flush()
        with pytest.raises(ConfigValidationError):
            load_config(f.name)
```

---

### Milestone 2 总验收

| 验收项 | 通过标准 |
|--------|----------|
| 提示音/通知 | 开始/结束/失败均有对应反馈 |
| 剪贴板恢复 | 10 次粘贴后剪贴板内容正确恢复率 100% |
| 服务守护 | kill 后 5 秒内自动重启 |
| 异常恢复 | ASR 服务断开后工具不崩溃，恢复后自动可用 |
| 连续运行 | 连续运行 30 分钟无内存泄漏（RSS 增长 < 10MB） |

---

## 4. Milestone 3: 体验优化（持续迭代）

### 4.1 目标

增强用户体验，支持更自然的语音输入方式。

### 4.1 任务列表（优先级排序）

| 优先级 | 任务 | 描述 | 预计工期 |
|--------|------|------|----------|
| P0 | VAD 自动截断 | 检测静音后自动停止录音 | 2 天 |
| P1 | 热词增强 | 支持自定义热词提升专业术语识别率 | 1 天 |
| P1 | 流式识别 | 边说边出字，降低感知延迟 | 3 天 |
| P2 | 命令词 | 支持"换行""删掉上一句"等语音命令 | 2 天 |
| P2 | 托盘图标 | 系统托盘显示录制状态 | 1 天 |

### 4.2 各任务验收条件

#### VAD 自动截断

- [ ] 说话结束后 1.5 秒内自动停止录音（无需等待松开按键）
- [ ] 静音超过 3 秒自动结束
- [ ] 噪声环境下不误触发停止
- [ ] 可以与按住说话模式共存（配置切换）

#### 热词增强

- [ ] config.yaml 中配置热词列表
- [ ] 热词通过 ASR 请求的 prompt 字段传递
- [ ] 至少 10 个自定义热词生效
- [ ] 不配置热词时不影响原有识别率

#### 流式识别

- [ ] 说话过程中实时显示部分识别结果
- [ ] 最终结果与一次性识别一致
- [ ] ASR 服务不支持流式时降级为一次性识别

#### 命令词

- [ ] "换行" -> 粘贴 \n
- [ ] "删掉上一句" -> 删除上一次粘贴的内容
- [ ] 非命令词文本正常粘贴
- [ ] 命令词列表可配置

---

## 5. 性能基准测试

### 5.1 延迟测试

| 指标 | 目标 | 测试方法 |
|------|------|----------|
| 快捷键触发延迟 | < 50ms | 按键时间戳 vs 录音开始时间戳 |
| ASR 识别延迟 | < 2s | 发送请求到收到响应 |
| 粘贴延迟 | < 200ms | 收到文本到 xdotool 执行完毕 |
| 端到端延迟 | < 3s | 松开按键到文本出现在屏幕 |

### 5.2 稳定性测试

| 指标 | 目标 | 测试方法 |
|------|------|----------|
| 单次成功率 | >= 98% | 连续 100 次操作统计 |
| 连续运行 | 24 小时无崩溃 | 后台运行 + 定时触发 |
| 内存泄漏 | RSS 增长 < 10MB/小时 | 1 小时连续使用后检查 |
| 剪贴板恢复率 | 100% | 50 次操作后验证 |

### 5.3 资源占用

| 指标 | 目标 |
|------|------|
| 空闲 CPU | < 1% |
| 空闲内存 | < 50MB |
| 录音时内存增量 | < 30MB |

---

## 6. 测试策略总览

### 6.1 测试分层

```
┌─────────────────────────┐
│   集成测试 (E2E)        │  main.py 启动后完整流程
├─────────────────────────┤
│   模块间集成测试         │  hotkey + recorder + asr_client
├─────────────────────────┤
│   单元测试               │  每个模块独立，mock 外部依赖
├─────────────────────────┤
│   手动验收测试           │  实际语音输入体验
└─────────────────────────┘
```

### 6.2 运行测试

```bash
# 运行所有单元测试
uv run pytest tests/ -v

# 运行特定模块测试
uv run pytest tests/test_state_machine.py -v
uv run pytest tests/test_asr_client_mock.py -v

# 运行带覆盖率
uv run pytest tests/ --cov=. --cov-report=term-missing

# 手动集成测试（需要 ASR 服务和麦克风）
uv run python main.py
```

### 6.3 CI 建议

```bash
# 本地 CI 模拟
uv run pytest tests/ -v --tb=short
uv run ruff check .
```

---

## 7. 发布检查清单

### MVP (Milestone 1) 发布前

- [ ] 所有单元测试通过
- [ ] 集成测试 20 次闭环成功率 >= 90%
- [ ] config.yaml 有完整注释说明
- [ ] README.md 包含安装和启动说明
- [ ] 无硬编码路径或 IP

### 稳定版 (Milestone 2) 发布前

- [ ] 所有 Milestone 2 验收项通过
- [ ] 30 分钟连续运行稳定
- [ ] systemd 服务文件可用
- [ ] 异常场景全部覆盖（ASR 不可用、麦克风不可用、无焦点窗口）

---

## 8. 开发顺序（推荐）

```
Week 1:
  Day 1  Morning: Task 1.1 state_machine.py
  Day 1  Afternoon: Task 1.2 audio_recorder.py
  Day 2  Morning: Task 1.3 asr_client.py
  Day 2  Afternoon: Task 1.4 text_injector.py
  Day 3  Morning: Task 1.5 hotkey_manager.py
  Day 3  Afternoon: Task 1.6 main.py 组装 + 集成测试

Week 2:
  Day 4: Task 2.1 notifier.py
  Day 5: Task 2.2 剪贴板恢复增强
  Day 6: Task 2.3 systemd 服务
  Day 7: Task 2.4 配置验证 + 全量回归测试

Week 3+:
  按优先级推进 Milestone 3 各任务
```
