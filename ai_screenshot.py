import argparse
import os
import sys
import signal
import logging
import atexit
import time
import subprocess
import requests
import pygetwindow as gw
import pyperclip
from pathlib import Path
from PIL import ImageGrab
from pynput import keyboard


# Constants
PID_FILE = Path.home() / ".ai-screenshooter.pid"
LOG_FILE = Path.home() / ".ai-screenshooter.log"
SCREENSHOT_DIR = Path.home() / ".ai-screenshooter" / "screenshots"
TIMEOUT_SECONDS = 5 * 60 * 60  # 5 hours

# Server URLs
PROD_URL = "https://service.tech4vision.net/ai-management-service/api/v1/sessions/code-challenge"
LOCAL_URL = "http://localhost:8082/api/v1/sessions/code-challenge"

# Global state
screenshot_list = []
API_TOKEN = None
API_URL = None
current_keys = set()
logger = logging.getLogger("ai-screenshooter")

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


# ============ PID File Management ============

def get_pid_from_file():
    """Read PID from file, return None if invalid."""
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text().strip())
        return pid if pid > 0 else None
    except (ValueError, IOError):
        return None


def is_process_running(pid):
    """Check if a process with the given PID is running."""
    try:
        os.kill(pid, 0)  # Signal 0 doesn't kill, just checks
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we don't have permission
        return True


def write_pid_file():
    """Write current PID to file."""
    PID_FILE.write_text(str(os.getpid()))


def cleanup_pid_file():
    """Remove PID file on exit."""
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
    except Exception:
        pass


# ============ Process Management ============

def kill_existing_process():
    """Kill any existing instance. Returns True if killed."""
    pid = get_pid_from_file()
    if not pid or not is_process_running(pid):
        cleanup_pid_file()
        return False

    try:
        os.kill(pid, signal.SIGTERM)
        # Wait up to 3 seconds for graceful shutdown
        for _ in range(30):
            time.sleep(0.1)
            if not is_process_running(pid):
                break
        else:
            # Force kill if still running
            os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass

    cleanup_pid_file()
    return True


def start_background_process(token, local):
    """Start a new background process using subprocess (avoids fork issues)."""
    # Build command to run this script with --daemon flag
    cmd = [
        sys.executable,
        "-m", "ai_screenshot",
        "start",
        "--token", token,
        "--daemon"  # Internal flag for the actual daemon process
    ]
    if local:
        cmd.append("--local")

    # Start the subprocess detached from terminal
    with open(os.devnull, 'w') as devnull:
        process = subprocess.Popen(
            cmd,
            stdout=devnull,
            stderr=devnull,
            stdin=devnull,
            start_new_session=True,  # Detach from terminal
        )

    print(f"Started background process (PID: {process.pid})")
    print(f"PID file: {PID_FILE}")
    print(f"Log file: {LOG_FILE}")


# ============ Signal Handlers ============

def handle_sigterm(signum, frame):
    """Handle SIGTERM for graceful shutdown."""
    logger.info("Received SIGTERM, shutting down...")
    cleanup_pid_file()
    sys.exit(0)


def handle_sigalrm(signum, frame):
    """Handle SIGALRM for auto-termination after timeout."""
    logger.info("5-hour timeout reached, auto-terminating...")
    cleanup_pid_file()
    sys.exit(0)


# ============ Logging Setup ============

def setup_logging(daemon_mode):
    """Configure logging based on mode."""
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    if daemon_mode:
        # File logging for daemon mode
        handler = logging.FileHandler(LOG_FILE)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    else:
        # Console logging for foreground mode
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(message)s'))

    logger.addHandler(handler)


# ============ Screenshot Functions ============

def get_active_window_bounds():
    """Returns the active window's bounds (x, y, width, height) in a cross-platform way."""
    time.sleep(0.1)

    try:
        active_window = gw.getActiveWindow()

        if isinstance(active_window, str):  # Ensure it's a window name
            geometry = gw.getWindowGeometry(active_window)
            if geometry:
                x, y, width, height = geometry
                logger.info(f"Active window detected: {active_window} at ({x}, {y}, {width}, {height})")
                return x, y, width, height

        elif active_window:
            x, y = active_window.left, active_window.top
            width, height = active_window.width, active_window.height
            logger.info(f"Active window detected: {active_window.title} at ({x}, {y}, {width}, {height})")
            return x, y, width, height
        else:
            logger.warning("No active window detected, defaulting to full screen.")

    except Exception as e:
        logger.error(f"Error detecting active window: {e}")

    return None


def capture_screenshot():
    global screenshot_list

    # Ensure screenshot directory exists
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    screenshot_path = SCREENSHOT_DIR / f"screenshot_{len(screenshot_list)}.jpg"

    try:
        logger.info("Refreshing active window detection...")
        window_bounds = get_active_window_bounds()

        if window_bounds:
            x, y, width, height = map(int, window_bounds)
            logger.info(f"Capturing active window at ({x}, {y}, {width}, {height})")
            screenshot = ImageGrab.grab(bbox=(x, y, x + width, y + height))
        else:
            logger.warning("No active window detected, capturing full screen.")
            screenshot = ImageGrab.grab()

        screenshot.convert("RGB").save(str(screenshot_path), "JPEG", quality=50)

        if screenshot_path.exists():
            screenshot_list.append(str(screenshot_path))
            logger.info(f"Screenshot captured: {screenshot_path}")
        else:
            logger.error(f"Screenshot capture failed: {screenshot_path}")
    except Exception as e:
        logger.error(f"Error capturing screenshot: {e}")


def send_screenshots():
    global screenshot_list
    if not API_TOKEN:
        logger.error("No API token provided!")
        return
    if not screenshot_list:
        logger.warning("No screenshots to send.")
        return

    files = []
    for f in screenshot_list:
        if os.path.exists(f):
            files.append(("files", (os.path.basename(f), open(f, "rb"))))
        else:
            logger.warning(f"Screenshot file not found: {f}")

    if not files:
        logger.warning("No valid screenshots to send.")
        return

    try:
        response = requests.post(
            API_URL,
            headers={"Authorization": f"Bearer {API_TOKEN}"},
            files=files,
        )

        if response.status_code == 200:
            logger.info("Screenshots uploaded successfully.")
            screenshot_list = []
        else:
            logger.error(f"Upload failed: {response.text}")
    except Exception as e:
        logger.error(f"Error uploading screenshots: {e}")


def send_clipboard_text():
    """Send clipboard content to Code tab API."""
    if not API_TOKEN:
        logger.error("No API token provided!")
        return

    try:
        text = pyperclip.paste()
        if not text or not text.strip():
            logger.warning("Clipboard is empty.")
            return

        response = requests.post(
            f"{API_URL}/chat",
            headers={
                "Authorization": f"Bearer {API_TOKEN}",
                "Content-Type": "application/json"
            },
            json={"message": text}
        )

        if response.status_code == 200:
            logger.info("Text sent to Code tab successfully.")
        else:
            logger.error(f"Failed to send text: {response.text}")
    except Exception as e:
        logger.error(f"Error sending clipboard text: {e}")


# ============ Keyboard Handlers ============

def on_press(key):
    current_keys.add(key)
    try:
        if key == keyboard.Key.down and keyboard.Key.esc in current_keys:
            logger.info("Capturing screenshot...")
            capture_screenshot()
        elif key == keyboard.Key.up and keyboard.Key.esc in current_keys:
            logger.info("Sending all screenshots...")
            send_screenshots()
        elif key == keyboard.Key.right and keyboard.Key.esc in current_keys:
            logger.info("Sending clipboard text to Code tab...")
            send_clipboard_text()
    except AttributeError:
        pass


def on_release(key):
    try:
        current_keys.remove(key)
    except KeyError:
        pass


# ============ CLI Commands ============

def cmd_start(args):
    """Handle the start command."""
    global API_TOKEN, API_URL

    # If --background flag, spawn a new process and exit
    if args.background:
        print("Starting in background mode...")
        killed = kill_existing_process()
        if killed:
            print("Killed existing instance.")

        start_background_process(args.token, args.local)
        return

    # If --daemon flag (internal), this is the actual daemon process
    is_daemon = getattr(args, 'daemon', False)

    if is_daemon:
        # Write PID file
        write_pid_file()
        atexit.register(cleanup_pid_file)

        # Set up logging to file
        setup_logging(daemon_mode=True)

        # Set 5-hour auto-termination timer
        signal.signal(signal.SIGALRM, handle_sigalrm)
        signal.alarm(TIMEOUT_SECONDS)
    else:
        setup_logging(daemon_mode=False)

    # Signal handler for graceful shutdown
    signal.signal(signal.SIGTERM, handle_sigterm)

    # Setup API config
    API_TOKEN = args.token
    API_URL = LOCAL_URL if args.local else PROD_URL

    server_mode = "LOCAL" if args.local else "PRODUCTION"
    logger.info("AI Screenshot CLI started.")
    logger.info(f"Server: {server_mode} ({API_URL})")
    logger.info("Press ESC + Down to capture a screenshot.")
    logger.info("Press ESC + Up to send all stored screenshots.")
    logger.info("Press ESC + Right to send clipboard text to Code tab.")
    if not is_daemon:
        logger.info("Running... (Press Ctrl + C to exit)")

    # Listen for hotkeys using pynput
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()


def cmd_status(args):
    """Handle the status command."""
    pid = get_pid_from_file()
    if pid and is_process_running(pid):
        print(f"ai-screenshooter is running (PID: {pid})")
        return 0
    else:
        print("ai-screenshooter is not running")
        if PID_FILE.exists():
            print(f"(stale PID file exists at {PID_FILE})")
        return 1


def cmd_stop(args):
    """Handle the stop command."""
    if kill_existing_process():
        print("ai-screenshooter stopped")
        return 0
    else:
        print("ai-screenshooter is not running")
        return 1


# ============ Main Entry Point ============

def main():
    parser = argparse.ArgumentParser(description="AI Screenshot CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # start command
    start_parser = subparsers.add_parser("start", help="Start listening for hotkeys")
    start_parser.add_argument("--token", required=True, help="API Token for authentication")
    start_parser.add_argument("--local", action="store_true", help="Use localhost server instead of production")
    start_parser.add_argument("--background", "-b", action="store_true", help="Run in background (daemon mode)")
    start_parser.add_argument("--daemon", action="store_true", help=argparse.SUPPRESS)  # Internal flag

    # status command
    subparsers.add_parser("status", help="Check if ai-screenshooter is running")

    # stop command
    subparsers.add_parser("stop", help="Stop the running ai-screenshooter instance")

    args = parser.parse_args()

    if args.command == "start":
        cmd_start(args)
    elif args.command == "status":
        sys.exit(cmd_status(args))
    elif args.command == "stop":
        sys.exit(cmd_stop(args))


if __name__ == "__main__":
    main()
