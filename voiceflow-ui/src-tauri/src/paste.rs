use std::io::Write;
use std::process::Command;

/// Save the currently active window ID via xdotool.
pub fn get_active_window() -> Option<String> {
    let output = Command::new("xdotool")
        .args(["getactivewindow"])
        .output()
        .ok()?;
    if output.status.success() {
        Some(String::from_utf8_lossy(&output.stdout).trim().to_string())
    } else {
        None
    }
}

/// Focus a specific window before pasting.
fn focus_window(window_id: &str) -> bool {
    Command::new("xdotool")
        .args(["windowfocus", "--sync", window_id])
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

pub fn inject_text(
    text: &str,
    shortcut: &str,
    restore_clipboard: bool,
    target_window: Option<&str>,
) -> bool {
    if text.is_empty() {
        log::warn!("inject_text: empty text");
        return false;
    }

    log::info!(
        "inject_text: text_len={}, shortcut={}, target_window={:?}",
        text.len(),
        shortcut,
        target_window
    );

    // Restore focus to the original window before pasting
    if let Some(wid) = target_window {
        if !focus_window(wid) {
            log::warn!("inject_text: failed to focus window {}", wid);
        }
        // Small delay for focus to take effect
        std::thread::sleep(std::time::Duration::from_millis(50));
    }

    let saved = if restore_clipboard {
        save_clipboard()
    } else {
        None
    };

    if !set_clipboard(text) {
        log::error!("inject_text: failed to set clipboard");
        return false;
    }
    std::thread::sleep(std::time::Duration::from_millis(100));

    if !send_paste(shortcut) {
        log::error!("inject_text: failed to send paste");
        return false;
    }
    std::thread::sleep(std::time::Duration::from_millis(100));

    log::info!("inject_text: paste sent successfully");

    if let Some(data) = saved {
        std::thread::sleep(std::time::Duration::from_millis(500));
        restore_clipboard_data(&data);
    }

    true
}

fn save_clipboard() -> Option<Vec<u8>> {
    let output = Command::new("xclip")
        .args(["-sel", "clip", "-o"])
        .output()
        .ok()?;
    if output.status.success() {
        Some(output.stdout)
    } else {
        None
    }
}

fn set_clipboard(text: &str) -> bool {
    Command::new("xclip")
        .args(["-sel", "clip"])
        .stdin(std::process::Stdio::piped())
        .spawn()
        .and_then(|mut child| {
            if let Some(stdin) = child.stdin.as_mut() {
                stdin.write_all(text.as_bytes())?;
            }
            child.wait()
        })
        .map(|s| s.success())
        .unwrap_or(false)
}

fn send_paste(shortcut: &str) -> bool {
    Command::new("xdotool")
        .args(["key", "--clearmodifiers", shortcut])
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

fn restore_clipboard_data(data: &[u8]) {
    let _ = Command::new("xclip")
        .args(["-sel", "clip"])
        .stdin(std::process::Stdio::piped())
        .spawn()
        .and_then(|mut child| {
            if let Some(stdin) = child.stdin.as_mut() {
                stdin.write_all(data)?;
            }
            child.wait()
        });
}
