#!/usr/bin/env python3
"""
News Agent Web Management Interface
Flask backend application for managing News Agent
"""

import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from threading import Lock

import yaml
from flask import Flask, jsonify, render_template, request

# Add src to path if running directly
if __name__ == "__main__" and __package__ is None:
    src_path = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(src_path))

# Get the directory of this file
current_dir = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(current_dir, 'templates'),
    static_folder=os.path.join(current_dir, 'static')
)

# Config path
CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "config" / "settings.yaml"

# Fetch news status
fetch_status = {
    "running": False,
    "last_result": None
}
fetch_lock = Lock()

# Config save status
config_save_status = {
    "running": False,
    "last_result": None
}
config_save_lock = Lock()


@app.route("/")
def index():
    """Render the main page"""
    return render_template("index.html")


@app.route("/api/config", methods=["GET"])
def api_get_config():
    """Get current config"""
    try:
        if not CONFIG_PATH.exists():
            return jsonify({"error": "Config file not found"}), 404

        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # Ensure cron times are strings (convert datetime objects or minutes if needed)
        cron_times = config.get("scheduler", {}).get("cron_times", [])
        cron_times_str = []
        for t in cron_times:
            if hasattr(t, 'strftime'):
                # It's a datetime/time object, convert to HH:MM string
                cron_times_str.append(t.strftime("%H:%M"))
            elif isinstance(t, int):
                # It's minutes since midnight (e.g., 690 = 11:30), convert to HH:MM
                hours = t // 60
                minutes = t % 60
                cron_times_str.append(f"{hours:02d}:{minutes:02d}")
            else:
                # Already a string
                cron_times_str.append(str(t))

        # Return only the parts we need for the UI
        ui_config = {
            "cron_times": ", ".join(cron_times_str),
            "email_recipients": ", ".join(config.get("email_163", {}).get("recipients", [])),
            "email_enabled": config.get("email_163", {}).get("enabled", False),
        }
        return jsonify(ui_config)
    except Exception as e:
        app.logger.error(f"Failed to get config: {e}")
        return jsonify({"error": str(e)}), 500


def run_save_config(data: dict):
    """Save config in background thread"""
    global config_save_status
    try:
        # Read existing config
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        else:
            config = {}

        # Update config
        if "scheduler" not in config:
            config["scheduler"] = {}

        # First, ensure existing cron times in config are strings
        if "cron_times" in config.get("scheduler", {}):
            fixed_cron_times = []
            for t in config["scheduler"]["cron_times"]:
                if hasattr(t, 'strftime'):
                    fixed_cron_times.append(t.strftime("%H:%M"))
                elif isinstance(t, int):
                    hours = t // 60
                    minutes = t % 60
                    fixed_cron_times.append(f"{hours:02d}:{minutes:02d}")
                else:
                    fixed_cron_times.append(str(t))
            config["scheduler"]["cron_times"] = fixed_cron_times

        if "cron_times" in data:
            config["scheduler"]["cron_times"] = [
                str(t.strip()) for t in data["cron_times"].split(",") if t.strip()
            ]

        if "email_163" not in config:
            config["email_163"] = {}
        if "email_recipients" in data:
            config["email_163"]["recipients"] = [
                r.strip() for r in data["email_recipients"].split(",") if r.strip()
            ]
        if "email_enabled" in data:
            config["email_163"]["enabled"] = data["email_enabled"]

        # Write back - ensure cron times are quoted so YAML parses as strings
        write_config_with_quoted_cron_times(CONFIG_PATH, config)

        # Restart scheduler to apply new config
        app.logger.info("Config saved, restarting scheduler...")
        stop_scheduler()
        start_scheduler()

        config_save_status["last_result"] = {"success": True}
    except Exception as e:
        app.logger.error(f"Failed to save config: {e}")
        config_save_status["last_result"] = {"success": False, "error": str(e)}
    finally:
        config_save_status["running"] = False


@app.route("/api/config", methods=["POST"])
def api_save_config():
    """Save config"""
    global config_save_status

    with config_save_lock:
        if config_save_status["running"]:
            return jsonify({"success": False, "message": "Already saving"}), 400

        config_save_status["running"] = True
        config_save_status["last_result"] = None

    thread = threading.Thread(target=run_save_config, args=(request.json,))
    thread.start()

    return jsonify({"success": True, "message": "Saving config..."})


@app.route("/api/config-save-status", methods=["GET"])
def api_config_save_status():
    """Get config save status"""
    return jsonify(config_save_status)


def write_config_with_quoted_cron_times(file_path: Path, config: dict):
    """Write config with cron times properly quoted to ensure YAML parses as strings"""
    import yaml
    from io import StringIO

    output = StringIO()

    # Write all sections except scheduler first
    scheduler_config = config.pop('scheduler', None)

    # Write the rest of the config
    yaml.safe_dump(config, output, allow_unicode=True, default_flow_style=False, sort_keys=False)
    content = output.getvalue()

    # Add scheduler section manually with quoted cron times
    if scheduler_config:
        content += '\nscheduler:\n'
        # Write timezone if present
        if 'timezone' in scheduler_config:
            content += f"  timezone: {scheduler_config['timezone']}\n"
        # Write cron times with quotes
        if 'cron_times' in scheduler_config:
            content += '  cron_times:\n'
            for time_str in scheduler_config['cron_times']:
                # Ensure it's a string and quote it
                content += f"    - '{str(time_str)}'\n"

    # Write to file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    # Restore config
    if scheduler_config:
        config['scheduler'] = scheduler_config


def get_scheduler_status() -> dict:
    """Get scheduler process status"""
    try:
        pid_file = Path(__file__).parent.parent.parent.parent / "logs" / "scheduler.pid"
        if not pid_file.exists():
            return {"running": False, "pid": None}

        pid = pid_file.read_text().strip()
        if not pid:
            return {"running": False, "pid": None}

        # Check if process is running
        try:
            result = subprocess.run(
                ["ps", "-p", pid],
                capture_output=True,
                text=True,
                timeout=5,
            )
            running = result.returncode == 0
            return {"running": running, "pid": pid if running else None}
        except:
            return {"running": False, "pid": None}
    except Exception as e:
        app.logger.error(f"Failed to get scheduler status: {e}")
        return {"running": False, "pid": None, "error": str(e)}


def start_scheduler() -> bool:
    """Start scheduler process"""
    try:
        project_root = Path(__file__).parent.parent.parent.parent
        start_script = project_root / "start_scheduler.sh"

        if not start_script.exists():
            return False

        subprocess.run(
            ["/bin/bash", str(start_script)],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=30,
        )
        time.sleep(2)
        return True
    except Exception as e:
        app.logger.error(f"Failed to start scheduler: {e}")
        return False


def stop_scheduler() -> bool:
    """Stop scheduler process"""
    try:
        project_root = Path(__file__).parent.parent.parent.parent
        stop_script = project_root / "stop_scheduler.sh"

        if not stop_script.exists():
            # Try to kill by PID file directly
            pid_file = project_root / "logs" / "scheduler.pid"
            if pid_file.exists():
                pid = pid_file.read_text().strip()
                if pid:
                    subprocess.run(["kill", "-9", pid], capture_output=True)
                    pid_file.unlink(missing_ok=True)
                    time.sleep(2)
                    return True
            return False

        subprocess.run(
            ["/bin/bash", str(stop_script)],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=30,
        )
        time.sleep(2)
        return True
    except Exception as e:
        app.logger.error(f"Failed to stop scheduler: {e}")
        return False


@app.route("/api/scheduler/status", methods=["GET"])
def api_scheduler_status():
    """Get scheduler status"""
    status = get_scheduler_status()
    return jsonify(status)


@app.route("/api/scheduler/start", methods=["POST"])
def api_scheduler_start():
    """Start scheduler"""
    success = start_scheduler()
    status = get_scheduler_status()
    return jsonify({"success": success, **status})


@app.route("/api/scheduler/stop", methods=["POST"])
def api_scheduler_stop():
    """Stop scheduler"""
    success = stop_scheduler()
    status = get_scheduler_status()
    return jsonify({"success": success, **status})


def run_fetch_news():
    """Run fetch news in background thread"""
    global fetch_status
    try:
        project_root = Path(__file__).parent.parent.parent.parent
        run_once_script = project_root / "src" / "run_once.py"

        result = subprocess.run(
            [sys.executable, str(run_once_script)],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=300,
        )

        fetch_status["last_result"] = {
            "success": result.returncode == 0,
            "stdout": result.stdout[-1000:],
            "stderr": result.stderr[-1000:],
        }
    except Exception as e:
        fetch_status["last_result"] = {
            "success": False,
            "error": str(e),
        }
    finally:
        fetch_status["running"] = False


@app.route("/api/fetch-news", methods=["POST"])
def api_fetch_news():
    """Trigger fetch news once"""
    global fetch_status

    with fetch_lock:
        if fetch_status["running"]:
            return jsonify({"success": False, "message": "Already running"}), 400

        fetch_status["running"] = True
        fetch_status["last_result"] = None

    thread = threading.Thread(target=run_fetch_news)
    thread.start()

    return jsonify({"success": True, "message": "Fetching news started"})


@app.route("/api/fetch-status", methods=["GET"])
def api_fetch_status():
    """Get fetch news status"""
    return jsonify(fetch_status)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5547, debug=False)
