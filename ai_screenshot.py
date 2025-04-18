import argparse
import os
import sys
import requests
import pygetwindow as gw
import time
from PIL import ImageGrab
from pynput import keyboard


screenshot_list = []
API_TOKEN = None

current_keys = set()

if sys.platform == "win32":
    import ctypes
    from ctypes import Structure, c_long
    windll = ctypes.windll

    class RECT(Structure):
        _fields_ = [("left", c_long), ("top", c_long), ("right", c_long), ("bottom", c_long)]
elif sys.platform == "darwin":
    from AppKit import NSWorkspace
    from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID
elif sys.platform == "linux":
    pass

def get_active_window_bounds():
    """Returns the active window's bounds (x, y, width, height) in a cross-platform way."""
    time.sleep(0.1)

    try:
        active_window = gw.getActiveWindow()

        if isinstance(active_window, str):  # Ensure it's a window name
            geometry = gw.getWindowGeometry(active_window)
            if geometry:
                x, y, width, height = geometry
                print(f"🖥️ Active window detected: {active_window} at ({x}, {y}, {width}, {height})")
                return x, y, width, height

        elif active_window:
            x, y = active_window.left, active_window.top
            width, height = active_window.width, active_window.height
            print(f"🖥️ Active window detected: {active_window.title} at ({x}, {y}, {width}, {height})")
            return x, y, width, height
        else:
            print("⚠️ No active window detected, defaulting to full screen.")

    except Exception as e:
        print(f"❌ Error detecting active window: {e}")

    return None


def capture_screenshot():
    global screenshot_list
    screenshot_path = f"screenshot_{len(screenshot_list)}.jpg"

    try:
        print("🔄 Refreshing active window detection...")
        window_bounds = get_active_window_bounds()  # Ensure fresh window detection

        if window_bounds:
            x, y, width, height = map(int, window_bounds)  # Convert all values to integers
            print(f"📸 Capturing active window at ({x}, {y}, {width}, {height})")
            screenshot = ImageGrab.grab(bbox=(x, y, x + width, y + height))
        else:
            print("⚠️ No active window detected, capturing full screen.")
            screenshot = ImageGrab.grab()

        screenshot.convert("RGB").save(screenshot_path, "JPEG", quality=50)

        if os.path.exists(screenshot_path):
            screenshot_list.append(screenshot_path)
            print(f"✅ Screenshot captured: {screenshot_path}")
        else:
            print(f"❌ Screenshot capture failed: {screenshot_path}")
    except Exception as e:
        print(f"❌ Error capturing screenshot: {e}")

def send_screenshots():
    global screenshot_list
    if not API_TOKEN:
        print("❌ No API token provided!")
        return
    if not screenshot_list:
        print("⚠️ No screenshots to send.")
        return

    files = []
    for f in screenshot_list:
        if os.path.exists(f):
            files.append(("files", (os.path.basename(f), open(f, "rb"))))
        else:
            print(f"⚠️ Warning: Screenshot file not found: {f}")

    if not files:
        print("⚠️ No valid screenshots to send.")
        return

    response = requests.post(
        "https://api.ai-management.tech4vision.io/api/v1/sessions/code-challenge",
        headers={"Authorization": f"Bearer {API_TOKEN}"},
        files=files,
    )

    if response.status_code == 200:
        print("✅ Screenshots uploaded successfully.")
        screenshot_list = []
    else:
        print(f"❌ Upload failed: {response.text}")

def on_press(key):
    current_keys.add(key)
    try:
        if key == keyboard.Key.down and keyboard.Key.esc in current_keys:
            print("📸 Capturing screenshot...")
            capture_screenshot()
        elif key == keyboard.Key.up and keyboard.Key.esc in current_keys:
            print("📤 Sending all screenshots...")
            send_screenshots()
    except AttributeError:
        pass

def on_release(key):
    try:
        current_keys.remove(key)
    except KeyError:
        pass

def main():
    parser = argparse.ArgumentParser(description="AI Screenshot CLI")
    parser.add_argument("start", help="Start listening for hotkeys")
    parser.add_argument("--token", required=True, help="API Token for authentication")

    args = parser.parse_args()
    global API_TOKEN
    API_TOKEN = args.token

    print("📸 AI Screenshot CLI started.")
    print("✅ Press ESC + ↓ to capture a screenshot.")
    print("✅ Press ESC + ↑ to send all stored screenshots.")
    print("📌 Running... (Press Ctrl + C to exit)")

    # Listen for hotkeys using pynput
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()  # Keep script running

if __name__ == "__main__":
    main()