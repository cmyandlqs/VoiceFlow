"""Test window_pos components — verify xrandr-based virtual screen detection."""

import subprocess
import sys


def test_xdotool_mouse():
    r = subprocess.run(
        ["xdotool", "getmouselocation", "--shell"],
        capture_output=True, text=True, timeout=2,
    )
    print(f"  raw: {r.stdout.strip()!r}")
    assert r.returncode == 0
    x = y = None
    for line in r.stdout.strip().splitlines():
        k, v = line.split("=", 1)
        if k == "X":
            x = int(v)
        elif k == "Y":
            y = int(v)
    assert x is not None and y is not None
    print(f"  PASS: mouse ({x}, {y})")


def test_xrandr_virtual_screen():
    r = subprocess.run(
        ["xrandr", "--query"],
        capture_output=True, text=True, timeout=2,
    )
    assert r.returncode == 0
    for line in r.stdout.splitlines():
        if "current" in line and "minimum" in line:
            print(f"  xrandr: {line.strip()}")
            idx = line.find("current")
            rest = line[idx:].split()
            w, h = int(rest[1]), int(rest[3].rstrip(","))
            assert w > 0 and h > 0
            print(f"  PASS: virtual screen {w}x{h}")
            # Verify mouse coordinates fit within
            r2 = subprocess.run(
                ["xdotool", "getmouselocation", "--shell"],
                capture_output=True, text=True, timeout=2,
            )
            mx = my = 0
            for l2 in r2.stdout.strip().splitlines():
                k, v = l2.split("=", 1)
                if k == "X":
                    mx = int(v)
                elif k == "Y":
                    my = int(v)
            assert 0 <= mx < w, f"mouse X={mx} outside screen W={w}"
            assert 0 <= my < h, f"mouse Y={my} outside screen H={h}"
            print(f"  PASS: mouse ({mx},{my}) within screen ({w}x{h})")
            return
    assert False, "xrandr did not return Screen line with 'current'"


def test_position_calc_dual_monitor():
    """Simulate dual 4K setup: 8192x2304 virtual screen."""
    sw, sh = 8192, 2304
    win_w, win_h = 140, 56

    # On second monitor
    mx, my = 5000, 1152
    x = min(mx + 16, sw - win_w - 8)
    y = min(my + 18, sh - win_h - 8)
    print(f"  2nd monitor: mouse ({mx},{my}) → window ({x},{y})")
    assert x == 5016 and y == 1170

    # Near right edge
    mx, my = 8100, 1152
    x = max(8, min(mx + 16, sw - win_w - 8))
    y = max(8, min(my + 18, sh - win_h - 8))
    print(f"  right edge: mouse ({mx},{my}) → window ({x},{y})")
    assert x == sw - win_w - 8

    # Near bottom edge
    mx, my = 4000, 2280
    x = max(8, min(mx + 16, sw - win_w - 8))
    y = max(8, min(my + 18, sh - win_h - 8))
    print(f"  bottom edge: mouse ({mx},{my}) → window ({x},{y})")
    assert y == sh - win_h - 8

    print("  PASS: all position calculations correct")


def test_sidecar_daemon():
    import os, json
    python = os.path.join(os.path.dirname(__file__), "..", ".venv/bin/python")
    daemon = os.path.join(os.path.dirname(__file__), "daemon.py")
    if not os.path.exists(python) or not os.path.exists(daemon):
        print("  SKIP: files not found")
        return

    proc = subprocess.Popen(
        [python, daemon],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "VOICEFLOW_CONFIG": os.path.join(os.path.dirname(__file__), "..", "config.yaml")},
    )
    ready = proc.stdout.readline().strip()
    print(f"  ready: {ready}")
    assert "ready" in ready

    proc.stdin.write(json.dumps({"type": "ping"}) + "\n")
    proc.stdin.flush()
    pong = proc.stdout.readline().strip()
    print(f"  pong: {pong}")
    assert "pong" in pong

    proc.terminate()
    proc.wait(timeout=3)
    print("  PASS")


def main():
    tests = [
        ("xdotool mouse location", test_xdotool_mouse),
        ("xrandr virtual screen size", test_xrandr_virtual_screen),
        ("position calc (dual monitor)", test_position_calc_dual_monitor),
        ("sidecar daemon", test_sidecar_daemon),
    ]
    passed = failed = 0
    for name, fn in tests:
        print(f"\n[Test] {name}")
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"  FAIL: {e}")
            failed += 1

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
