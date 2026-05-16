# 语音输入项目 - 粘贴重复问题分析与解决方案

## 问题描述

用户使用语音输入时，识别出的文本会被粘贴两次到目标位置。

## 根因分析

### 当前实现问题

在 `text_injector.py` 的 `_send_paste()` 方法中：

```python
def _send_paste(self) -> None:
    for shortcut in [self.paste_shortcut, "ctrl+shift+v"]:
        if shortcut:
            subprocess.run(
                ["xdotool", "key", "--clearmodifiers", shortcut],
                check=False, timeout=2,
            )
            time.sleep(0.05)
```

**问题**：代码依次发送两个粘贴快捷键
1. 用户配置的快捷键（如 `ctrl+v`）
2. 硬编码的 `ctrl+shift+v`

**结果**：每次粘贴操作都会执行两次，导致重复粘贴。

### 设计初衷

用户的原始需求是合理的：
- `ctrl+v`：大多数应用（浏览器、编辑器、IM等）
- `ctrl+shift+v`：终端类应用（Gnome Terminal、Konsole等）

希望**兼容所有场景**，但实现方式导致了问题。

---

## 方案评估

### 方案 1：检测粘贴是否成功（用户提出的方案）

**思路**：
1. 先尝试 `ctrl+v`
2. 检测是否成功
3. 如果失败，再尝试 `ctrl+shift+v`

**可行性评估**：

| 检测方法 | 可行性 | 问题 |
|---------|--------|------|
| 检查剪贴板内容变化 | ❌ 不可靠 | 粘贴操作通常不改变剪贴板 |
| 检查 xdotool 返回值 | ❌ 无效 | 只表示命令发送成功，不代表应用处理了 |
| 检测光标位置文本变化 | ❌ 太复杂 | 需要获取粘贴前后状态，不同应用差异巨大 |
| 屏幕OCR识别 | ❌ 太重 | 性能差，不稳定，误识别率高 |

**结论**：**不可行**。粘贴操作发生在目标应用内部，没有可靠的方法从外部检测是否成功。

---

### 方案 2：智能检测终端窗口

**思路**：根据当前窗口类型自动选择快捷键

```python
TERMINAL_CLASSES = {
    "gnome-terminal", "konsole", "xfce4-terminal",
    "alacritty", "kitty", "XTerm", "urxvt"
}

def _detect_terminal(self) -> bool:
    result = subprocess.run(
        ["xdotool", "getactivewindow", "getwindowclassname"],
        capture_output=True, text=True
    )
    window_class = result.stdout.strip().lower()
    return any(term in window_class for term in TERMINAL_CLASSES)
```

**可行性评估**：

| 场景 | 识别难度 | 说明 |
|------|----------|------|
| Gnome Terminal / Konsole | ✅ 容易 | 标准终端类名 |
| VS Code 内置终端 | ❌ 困难 | 窗口类名是 `code`，无法区分是编辑器还是终端 |
| Cloud Code / Codex | ❌ 困难 | Electron 应用，类名不确定 |
| 浏览器中的 Cloud Shell | ❌ 不可能 | 窗口类名是浏览器，无法知道里面是终端 |
| Flatpak/Snap 应用 | ⚠️ 中等 | 类名带前缀（如 `org.gnome.Terminal`） |
| 远程桌面/VM中的终端 | ❌ 不可能 | 只能检测到 RDP/VM 窗口 |
| 微信 / Discord | ✅ 容易 | 但这些应用不需要特殊处理 |

**结论**：**部分可行，但边界情况多**。对于复杂场景（VS Code终端、浏览器SSH等）无法准确识别。

---

### 方案 3：双热键模式（推荐）

**思路**：用不同热键区分粘贴模式

| 热键 | 粘贴方式 | 适用场景 |
|------|----------|----------|
| F10 | ctrl+v | 大多数应用 |
| F11 | ctrl+shift+v | 终端、VS Code终端、浏览器SSH等 |

**优点**：
- ✅ 完全可靠，不依赖猜测
- ✅ 覆盖所有场景
- ✅ 实现简单，不易出 bug
- ✅ 用户完全掌控

**缺点**：
- 需要记住两个热键
- 初期可能有学习成本

---

### 方案 4：模式切换热键

**思路**：用一个热键切换粘贴模式

- **F10**：录音 + 使用当前模式粘贴
- **F9**：切换粘贴模式（普通/终端），并通知用户

**优点**：
- ✅ 只需要一个录音热键
- ✅ 可以通过通知提示当前模式

**缺点**：
- 需要手动切换模式
- 可能忘记当前是哪个模式

---

## 推荐方案

**方案 3（双热键）** 是最稳妥的选择：

1. **F10** = 普通粘贴（ctrl+v）
2. **F11** = 终端粘贴（ctrl+shift+v）

### 实现要点

修改 `hotkey_manager.py` 支持多个热键：

```python
class HotkeyManager:
    def __init__(self, combos: dict[str, Callable]):
        # combos = {"f10": on_f10_press, "f11": on_f11_press}
        ...
```

修改 `main.py` 根据热键选择粘贴方式：

```python
def _on_f10_release(self):
    # 普通粘贴
    result = self.asr.transcribe(wav_path)
    self.injector.inject(result.text, shortcut="ctrl+v")

def _on_f11_release(self):
    # 终端粘贴
    result = self.asr.transcribe(wav_path)
    self.injector.inject(result.text, shortcut="ctrl+shift+v")
```

---

## 配置文件更新

```yaml
hotkey:
  mode: hold_to_talk
  # 普通粘贴热键
  combo: f10
  # 终端粘贴热键（可选）
  terminal_combo: f11

paste:
  enabled: true
  method: clipboard
  # 默认粘贴方式
  default_shortcut: ctrl+v
  # 终端粘贴方式
  terminal_shortcut: ctrl+shift+v
  restore_clipboard: true
```

---

## 总结

| 方案 | 可靠性 | 复杂度 | 推荐度 |
|------|--------|--------|--------|
| 检测粘贴成功 | ❌ 不可行 | - | 不推荐 |
| 智能检测终端 | ⚠️ 部分可行 | 中 | 复杂场景不可靠 |
| 双热键模式 | ✅ 完全可靠 | 低 | **强烈推荐** |
| 模式切换热键 | ✅ 可靠 | 中 | 可选 |

**最终建议**：采用双热键模式（F10 / F11），简单可靠，覆盖所有场景。
