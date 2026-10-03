#!/usr/bin/env python3
"""
J.A.R.V.I.S. / F.R.I.D.A.Y. - Autonomous Voice AI Agent for macOS (Apple Silicon M5)
Full-featured interactive command center & voice agent with:
- Interactive Arc Reactor HUD with real-time controls, app launcher & speed-dial
- Embedded REST API server (port 8765) for bidirectional HUD communication
- Direct Chrome searches ("search manga on chrome", "google quantum computing")
- WhatsApp message sending and voice calling with auto-send (by name or phone number)
- Instagram DMs & Messaging ("send message on ig to username", "dm username on instagram")
- Native Phone & FaceTime calling ("call Dad", "facetime Mom")
- Chrome tab management ("new tab", "close tab", "reload")
- Hardware Telemetry & Sleep/Wake Watchdog
- Autonomous Ollama Tool-Calling Core
"""

import functools
import http.server
import json
import os
import re
import shutil
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse

# -----------------------------------------------------------------------------
# Environment & PATH Resolution for Apple Silicon
# -----------------------------------------------------------------------------
for path in ["/opt/homebrew/bin", "/opt/homebrew/sbin", os.path.expanduser("~/.local/bin")]:
    if path not in os.environ.get("PATH", "").split(os.path.pathsep) and os.path.isdir(path):
        os.environ["PATH"] = f"{path}{os.path.pathsep}{os.environ.get('PATH', '')}"

# Auto-reexec into local virtualenv or Homebrew Python if run from unconfigured Python
try:
    import psutil
    import requests
    import speech_recognition as sr
except ModuleNotFoundError:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    venv_py = os.path.join(script_dir, ".venv", "bin", "python3")
    brew_py = "/opt/homebrew/bin/python3"
    target_py = None
    if os.path.exists(venv_py) and sys.executable != venv_py:
        target_py = venv_py
    elif os.path.exists(brew_py) and sys.executable != brew_py:
        target_py = brew_py

    if target_py:
        os.execv(target_py, [target_py] + sys.argv)
    else:
        print("[!] Missing required libraries (psutil, requests, speech_recognition).")
        print("    Please run: ./setup.sh to set up your environment.")
        sys.exit(1)

# -----------------------------------------------------------------------------
# Agent Configuration
# -----------------------------------------------------------------------------
LM_STUDIO_URL = os.environ.get("LM_STUDIO_HOST", "http://127.0.0.1:1234/v1")
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
MODEL = "nvidia-nemotron-3-nano-4b"
MAX_HISTORY_TURNS = 6
HUD_PORT = 8765
CONTACTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "contacts.json")

# Portals & Academic Links
WEBSITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "github": "https://www.github.com",
    "moodle": "https://cet.iitp.ac.in/moodle",
    "iit patna": "https://cet.iitp.ac.in/moodle",
    "webmail": "https://outlook.office.com",
    "outlook web": "https://outlook.office.com",
    "edutinker": "https://iitp.edutinker.com",
    "reddit": "https://www.reddit.com",
    "linkedin": "https://www.linkedin.com",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "netflix": "https://www.netflix.com",
    "coursera": "https://www.coursera.org",
    "spotify": "https://open.spotify.com",
    "instagram": "https://www.instagram.com",
    "ig": "https://www.instagram.com",
}

# Spoken aliases mapping to macOS apps
APP_ALIASES = {
    "chrome": "google chrome",
    "google chrome": "google chrome",
    "vscode": "visual studio code",
    "vs code": "visual studio code",
    "code": "visual studio code",
    "visual studio code": "visual studio code",
    "settings": "system settings",
    "system settings": "system settings",
    "calc": "calculator",
    "calculator": "calculator",
    "teams": "microsoft teams",
    "microsoft teams": "microsoft teams",
    "outlook": "microsoft outlook",
    "microsoft outlook": "microsoft outlook",
    "excel": "microsoft excel",
    "microsoft excel": "microsoft excel",
    "powerpoint": "microsoft powerpoint",
    "microsoft powerpoint": "microsoft powerpoint",
    "ppt": "microsoft powerpoint",
    "word": "microsoft word",
    "microsoft word": "microsoft word",
    "activity": "activity monitor",
    "activity monitor": "activity monitor",
    "task manager": "activity monitor",
    "notes": "notes",
    "apple notes": "notes",
    "music": "music",
    "apple music": "music",
    "terminal": "terminal",
    "safari": "safari",
    "whatsapp": "whatsapp",
    "telegram": "telegram",
    "slack": "slack",
    "chatgpt": "chatgpt",
    "claude": "claude",
    "edutinker": "edutinker",
    "messages": "messages",
    "imessage": "messages",
    "mail": "mail",
    "calendar": "calendar",
    "maps": "maps",
    "weather": "weather",
    "reminders": "reminders",
    "steam": "steam",
    "prime video": "prime video",
    "prime": "prime video",
}

# --- AGENT SYSTEM PROMPTS ---
JARVIS_SYSTEM_PROMPT = """
You are J.A.R.V.I.S., an autonomous, witty, refined, and highly capable AI voice agent for Deepak Siwach on his MacBook Air M5.
Deepak is studying AI & Cyber Security at IIT Patna and is located in Gurugram, India.

Persona & Rules:
- Address the user as 'Sir' or 'Mr. Siwach'.
- Speak with British butler elegance, sharp intellect, and subtle humor.
- You have autonomous access to tools: web search in Chrome, WhatsApp messaging/calling, Instagram DMs, tab management, opening/closing apps, system diagnostics, timers, notes, volume, screenshots, and phone calls.
- ALWAYS invoke the appropriate tool when the user requests an action, search, message, call, or system status.
- Keep spoken replies concise (1-3 sentences) for natural voice flow.
- Reply in plain conversational text only: absolutely NO markdown syntax (no asterisks, hash marks, bullet lists, emojis, or code blocks), because your response is spoken aloud.
"""

FRIDAY_SYSTEM_PROMPT = """
You are F.R.I.D.A.Y., a tactical, warm, sharp, and highly loyal Irish-style autonomous voice agent for Deepak Siwach on his MacBook Air M5.
Deepak is studying AI & Cyber Security at IIT Patna and is located in Gurugram, India.

Persona & Rules:
- Address the user as 'Boss' or 'Deepak'.
- Speak with direct, tactical clarity, warmth, and keen observation.
- You have autonomous access to tools: web search in Chrome, WhatsApp messaging/calling, Instagram DMs, tab management, opening/closing apps, system diagnostics, timers, notes, volume, screenshots, and phone calls.
- ALWAYS invoke the appropriate tool when the user requests an action, search, message, call, or system status.
- Keep spoken replies concise (1-3 sentences) for natural voice flow.
- Reply in plain conversational text only: absolutely NO markdown syntax (no asterisks, hash marks, bullet lists, emojis, or code blocks), because your response is spoken aloud.
"""

# Tool schemas provided to Ollama function calling
OLLAMA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_web_in_browser",
            "description": "Searches for a query directly on Google Chrome, YouTube, Wikipedia, Reddit, GitHub, or Amazon and displays results in a new tab",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search term or query (e.g. 'manga', 'cybersecurity fundamentals', 'lofi beats')",
                    },
                    "platform": {
                        "type": "string",
                        "enum": ["chrome", "google", "youtube", "wikipedia", "reddit", "github", "amazon", "spotify"],
                        "description": "Platform to search on. Defaults to 'chrome' (Google Search)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_whatsapp_message",
            "description": "Sends a WhatsApp message to a contact name or phone number",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact": {
                        "type": "string",
                        "description": "Name of contact (e.g. 'Dad', 'Mom', 'Aryan') or phone number with country code",
                    },
                    "message": {
                        "type": "string",
                        "description": "Message text to send",
                    },
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "make_whatsapp_call",
            "description": "Initiates a WhatsApp voice call to a contact or phone number",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact": {
                        "type": "string",
                        "description": "Name of contact or phone number to call on WhatsApp",
                    }
                },
                "required": ["contact"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_instagram_message",
            "description": "Opens Instagram DMs to send a message to a user or opens the DM inbox",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "Instagram handle or username (e.g. 'deepak', 'rahul')",
                    },
                    "message": {
                        "type": "string",
                        "description": "Message text to send",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manage_chrome_tabs",
            "description": "Controls Google Chrome tabs (open new tab, close current tab, or reload page)",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["new", "close", "reload"],
                        "description": "Tab action to perform",
                    }
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_application",
            "description": "Opens an installed macOS application on the user's Mac",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Name of the application to open, e.g. 'Google Chrome', 'Visual Studio Code', 'Calculator', 'Notes', 'Terminal', 'WhatsApp'",
                    }
                },
                "required": ["app_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "close_application",
            "description": "Closes or quits a running macOS application",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Name of the application to close, e.g. 'Safari', 'Google Chrome', 'Calculator'",
                    }
                },
                "required": ["app_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "system_diagnostics",
            "description": "Gets real-time telemetry from MacBook Air M5 (Apple M5 chip architecture, CPU utilization, unified memory usage, and battery power status)",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Captures a screenshot of the macOS screen and saves it to Desktop",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_contact",
            "description": "Saves or updates a contact's phone number in Jarvis's local address book",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Contact name (e.g. 'Dad', 'Mom', 'Friend')"},
                    "phone": {"type": "string", "description": "Phone number with country code (e.g. '+919812345678')"},
                },
                "required": ["name", "phone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Fetches current weather and forecast for a specified city (defaults to Gurugram)",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City or region name, e.g. 'Gurugram', 'Patna', 'Delhi'",
                    }
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_timer",
            "description": "Sets a countdown timer that rings and speaks an alert when completed",
            "parameters": {
                "type": "object",
                "properties": {
                    "minutes": {
                        "type": "number",
                        "description": "Duration in minutes (e.g. 10, 25, 0.5)",
                    },
                    "label": {
                        "type": "string",
                        "description": "Label for the timer (e.g. 'study session', 'tea break')",
                    },
                },
                "required": ["minutes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "take_note",
            "description": "Saves a quick note, study reminder, or memo to the user's local notes folder",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Short title or subject of the note",
                    },
                    "content": {
                        "type": "string",
                        "description": "Body text of the note",
                    },
                },
                "required": ["title", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "control_volume",
            "description": "Controls macOS system audio output volume or mute status",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["set", "mute", "unmute", "up", "down"],
                        "description": "The volume action to perform",
                    },
                    "level": {
                        "type": "integer",
                        "description": "Volume percentage from 0 to 100 when action is 'set'",
                    },
                },
                "required": ["action"],
            },
        },
    },
]


def has(text, *patterns):
    return any(re.search(rf"\b{p}\b", text) for p in patterns)


def installed_voices():
    try:
        out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
        return {line.split()[0] for line in out.splitlines() if line.strip()}
    except Exception:
        return set()


# -----------------------------------------------------------------------------
# Embedded HTTP Server for Interactive HUD
# -----------------------------------------------------------------------------
class AgentHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, agent_instance=None, **kwargs):
        self.agent = agent_instance
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args):
        # Silence verbose request logs in terminal
        return

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "index.html")
            try:
                with open(ui_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self.send_error(500, f"Error reading UI: {e}")
        elif parsed.path in ("/api/state", "/state.json"):
            state = self.agent.get_current_state()
            data = json.dumps(state).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)
        elif parsed.path == "/api/apps":
            apps_dict = self.agent.find_installed_apps()
            unique_apps = {}
            for k, v in apps_dict.items():
                disp, path = v
                if disp not in unique_apps:
                    unique_apps[disp] = {"name": disp, "id": k, "path": path}
            apps_list = sorted(list(unique_apps.values()), key=lambda x: x["name"].lower())
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"apps": apps_list}).encode("utf-8"))
        elif parsed.path == "/api/notes":
            notes = self.agent.get_all_notes()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"notes": notes}).encode("utf-8"))
        elif parsed.path == "/api/contacts":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"contacts": self.agent.contacts}).encode("utf-8"))
        elif parsed.path == "/api/logs":
            logs = self.agent.get_log_history()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            eng = self.agent.get_active_engine_info()
            self.wfile.write(json.dumps({
                "logs": logs,
                "pid": os.getpid(),
                "model": f"{eng['engine']} — {eng['model']}",
                "engine": eng["engine"],
                "engine_active": eng["active"],
                "ollama_active": eng["active"]
            }).encode("utf-8"))
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            payload = json.loads(body)
        except Exception:
            payload = {}

        if parsed.path == "/api/command":
            cmd = payload.get("command", "")
            source = payload.get("source", "typed")
            if cmd:
                reply = self.agent.process_input_command(cmd, source=source)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                if isinstance(reply, dict) and reply.get("status") == "ignored":
                    self.wfile.write(json.dumps(reply).encode("utf-8"))
                else:
                    self.wfile.write(json.dumps({"status": "ok", "command": cmd, "reply": reply or "Command executed."}).encode("utf-8"))
            else:
                self.send_response(400)
                self.end_headers()
        elif parsed.path == "/api/action":
            action = payload.get("action")
            reply = self.agent.execute_direct_action(action, payload)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "action": action, "reply": reply}).encode("utf-8"))
        elif parsed.path == "/api/apps/launch":
            app_name = payload.get("app_name", "")
            res = self.agent.tool_open_app(app_name)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "message": res}).encode("utf-8"))
        elif parsed.path == "/api/notes":
            title = payload.get("title", "Note")
            content = payload.get("content", "")
            res = self.agent.tool_take_note(title, content)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "message": res, "notes": self.agent.get_all_notes()}).encode("utf-8"))
        elif parsed.path == "/api/notes/delete":
            filename = payload.get("filename", "")
            res = self.agent.delete_note(filename)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "deleted": res, "notes": self.agent.get_all_notes()}).encode("utf-8"))
        elif parsed.path == "/api/contacts":
            name = payload.get("name", "")
            phone = payload.get("phone", "")
            res = self.agent.tool_save_contact(name, phone)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "message": res, "contacts": self.agent.contacts}).encode("utf-8"))
        elif parsed.path == "/api/contacts/delete":
            name = payload.get("name", "")
            res = self.agent.delete_contact(name)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "deleted": res, "contacts": self.agent.contacts}).encode("utf-8"))
        elif parsed.path == "/api/timer/start":
            mins = float(payload.get("minutes", 15))
            lbl = payload.get("label", "study session")
            res = self.agent.tool_set_timer(mins, lbl)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "message": res}).encode("utf-8"))
        elif parsed.path == "/api/timer/cancel":
            self.agent.active_timers.clear()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "message": "All timers cancelled."}).encode("utf-8"))
        elif parsed.path == "/api/terminal":
            cmd = payload.get("command", "")
            if cmd:
                try:
                    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15, cwd=os.path.dirname(os.path.abspath(__file__)))
                    out = proc.stdout if proc.stdout else proc.stderr
                    code = proc.returncode
                except Exception as e:
                    out = str(e)
                    code = 1
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "output": out or "(Executed with no output)", "exit_code": code}).encode("utf-8"))
            else:
                self.send_response(400)
                self.end_headers()
        elif parsed.path == "/api/backend/restart":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "message": "Restarting agent..."}).encode("utf-8"))
            def do_restart():
                time.sleep(0.5)
                os.execv(sys.executable, [sys.executable] + sys.argv)
            threading.Thread(target=do_restart, daemon=True).start()
        elif parsed.path == "/api/backend/shutdown":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "message": "Shutting down agent..."}).encode("utf-8"))
            def do_shutdown():
                time.sleep(0.5)
                os._exit(0)
            threading.Thread(target=do_shutdown, daemon=True).start()
        else:
            self.send_response(404)
            self.end_headers()


# -----------------------------------------------------------------------------
# Main Voice Agent Core
# -----------------------------------------------------------------------------
class VoiceAgent:
    def __init__(self, persona="jarvis", use_gui=True):
        self.persona = persona.lower()
        is_jarvis = self.persona == "jarvis"
        self.system_prompt = JARVIS_SYSTEM_PROMPT if is_jarvis else FRIDAY_SYSTEM_PROMPT
        self.title_name = "J.A.R.V.I.S." if is_jarvis else "F.R.I.D.A.Y."
        self.salutation = "Sir" if is_jarvis else "Boss"
        self.use_gui = use_gui

        preferred = "Daniel" if is_jarvis else "Moira"
        available = installed_voices()
        self.voice = preferred if preferred in available else None

        self.history = []
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self._ollama_proc = None
        self.active_timers = []
        self._watchdog_running = False
        self.load_contacts()
        self.current_status = "SYSTEM ONLINE"
        self.recent_message = None
        self.last_msg_id = 0
        self.has_microphone = False
        self.log_history = []
        self.add_log(f"{self.title_name} autonomous core initialized (PID: {os.getpid()}).")

    # =========================================================================
    # Embedded HTTP Server Lifecycle & Logging
    # =========================================================================
    def add_log(self, msg):
        ts = time.strftime("%H:%M:%S")
        entry = f"[{ts}] {msg}"
        self.log_history.append(entry)
        if len(self.log_history) > 300:
            self.log_history.pop(0)

    def get_log_history(self):
        return list(self.log_history)

    def get_active_engine_info(self):
        """Detects whether LM Studio (Nemotron) or Ollama is online."""
        # 1. Check LM Studio on port 1234
        try:
            r = requests.get(f"{LM_STUDIO_URL}/models", timeout=0.8)
            if r.status_code == 200:
                data = r.json().get("data", [])
                model_name = "Nemotron"
                if data:
                    for m in data:
                        m_id = m.get("id", "")
                        if "nemotron" in m_id.lower():
                            model_name = m_id
                            break
                    else:
                        model_name = data[0].get("id", "Nemotron")
                return {"active": True, "engine": "LM Studio", "model": model_name, "type": "lm_studio"}
        except Exception:
            pass

        # 2. Check Ollama on port 11434 (secondary fallback)
        try:
            r = requests.get(OLLAMA_URL, timeout=0.8)
            if r.status_code == 200:
                return {"active": True, "engine": "Ollama", "model": "llama3.2", "type": "ollama"}
        except Exception:
            pass

        return {"active": False, "engine": "LM Studio (Offline)", "model": "Nemotron (Port :1234)", "type": "none"}

    def is_ollama_active(self):
        return self.get_active_engine_info()["active"]

    def start_http_server(self):
        global HUD_PORT
        for port in [HUD_PORT, 8766, 8767, 8768]:
            try:
                handler = functools.partial(AgentHTTPHandler, agent_instance=self)
                socketserver.TCPServer.allow_reuse_address = True
                httpd = socketserver.TCPServer(("127.0.0.1", port), handler)
                t = threading.Thread(target=httpd.serve_forever, daemon=True)
                t.start()
                HUD_PORT = port
                print(f"📡 Interactive Mission Control Server active at: http://127.0.0.1:{HUD_PORT}")
                self.add_log(f"Mission Control Server listening on http://127.0.0.1:{HUD_PORT}")
                return True
            except Exception:
                continue
        print("[Notice: Embedded HTTP server could not bind on ports 8765-8768]")
        return False

    def is_addressed_to_assistant(self, text, source="typed"):
        if source in ("typed", "tile", "button", "shortcut"):
            return True

        clean = text.lower().strip()
        wake_words = ["jarvis", "friday", "hey jarvis", "hey friday", "ok jarvis", "ok friday"]
        has_wake_word = any(re.search(rf"\b{w}\b", clean) for w in wake_words)

        third_party_targets = [
            "mom", "mother", "mummy", "dad", "father", "papa", "bhai", "bro",
            "brother", "sister", "yaar", "dost", "friend", "friends", "guys",
            "everyone", "rahul", "aryan", "uncle", "aunty"
        ]
        addressing_third_party = any(re.search(rf"\b{tp}\b", clean) for tp in third_party_targets)

        if addressing_third_party and not has_wake_word:
            return False

        direct_system_commands = [
            "system status", "diagnostics", "telemetry", "take a screenshot",
            "screenshot", "lock screen", "mute", "unmute", "volume up", "volume down",
            "open moodle", "open webmail", "search manga on chrome", "play lofi beats",
            "open chrome", "open vs code", "open whatsapp", "open terminal", "open calculator",
            "open notes", "open spotify", "set a timer", "take a note"
        ]
        is_direct_command = any(clean.startswith(c) or c in clean for c in direct_system_commands)

        if source in ("voice_push_to_talk", "voice"):
            if addressing_third_party and not has_wake_word:
                return False
            if has_wake_word or is_direct_command:
                return True
            ai_question_starters = [
                "what is", "what are", "how to", "how do", "explain", "define", "who is",
                "where is", "search for", "tell me about", "calculate", "convert"
            ]
            if any(clean.startswith(s) for s in ai_question_starters):
                return True
            return False

        return True

    def process_input_command(self, cmd_text, source="typed"):
        """Processes command sent from UI or voice and speaks response."""
        if not self.is_addressed_to_assistant(cmd_text, source=source):
            self.add_log(f"AMBIENT CONVERSATION FILTERED: '{cmd_text}'")
            self.update_ui_state("STANDBY")
            return {"status": "ignored", "reason": "ambient_conversation", "text": cmd_text}

        self.update_ui_state("THINKING", user_speech=cmd_text)
        handled = self.fast_intent_router(cmd_text)
        if not handled:
            reply = self.agentic_reasoning_loop(cmd_text)
            self.speak(reply)
            self.play_sound("complete", wait=False)
            return reply
        return self.recent_message.get("text") if self.recent_message else "Executing command."

    def execute_direct_action(self, action_name, payload):
        """Handles direct interactive tile clicks from the HUD."""
        if action_name == "screenshot":
            res = self.tool_take_screenshot()
            reply = f"{res.rstrip('.')}, {self.salutation}."
            threading.Thread(target=self.speak, args=(reply,), daemon=True).start()
            return reply
        elif action_name == "lock":
            self.play_sound("lock", wait=False)
            self.tool_lock_screen()
            reply = f"Screen locked, {self.salutation}."
            threading.Thread(target=self.speak, args=(reply,), daemon=True).start()
            return reply
        elif action_name == "toggle_mute":
            return self.tool_control_volume("mute")
        elif action_name == "volume":
            lvl = payload.get("level", 80)
            return self.tool_control_volume("set", lvl)
        elif action_name == "switch_persona":
            p = payload.get("persona", "jarvis")
            self.persona = p
            is_j = (p == "jarvis")
            self.system_prompt = JARVIS_SYSTEM_PROMPT if is_j else FRIDAY_SYSTEM_PROMPT
            self.title_name = "J.A.R.V.I.S." if is_j else "F.R.I.D.A.Y."
            self.salutation = "Sir" if is_j else "Boss"
            self.voice = "Daniel" if is_j else "Moira"
            reply = f"{self.title_name} persona online, {self.salutation}."
            threading.Thread(target=self.speak, args=(reply,), daemon=True).start()
            return reply
        return "Action acknowledged"

    # =========================================================================
    # Contacts Management
    # =========================================================================
    def load_contacts(self):
        self.contacts = {}
        if os.path.exists(CONTACTS_FILE):
            try:
                with open(CONTACTS_FILE, "r", encoding="utf-8") as f:
                    self.contacts = json.load(f)
            except Exception:
                self.contacts = {}

    def save_contacts(self):
        try:
            with open(CONTACTS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.contacts, f, indent=2)
        except Exception:
            pass

    def resolve_contact_phone(self, contact_name):
        if not contact_name:
            return None
        c = contact_name.lower().strip()
        if c in self.contacts and self.contacts[c]:
            return self.contacts[c]
        for k, v in self.contacts.items():
            if (c in k or k in c) and v:
                return v
        clean_num = re.sub(r"[^\d+]", "", c)
        if len(clean_num) >= 7:
            return clean_num
        return None

    def tool_save_contact(self, name, phone):
        clean_name = name.lower().strip()
        clean_phone = re.sub(r"[^\d+]", "", phone)
        self.contacts[clean_name] = clean_phone
        self.save_contacts()
        self.update_ui_state("STANDBY", action=f"Saved contact {name}: {clean_phone}")
        return f"Contact {name.title()} saved with phone number {clean_phone}."

    # =========================================================================
    # GUI HUD Synchronization
    # =========================================================================
    def get_current_state(self):
        try:
            mem = psutil.virtual_memory()
            used_gb = round(mem.used / (1024**3), 1)
            total_gb = round(mem.total / (1024**3))

            bat_str = self.get_battery_status()
            bat_pct = "80%"
            power = "AC Power"
            m = re.search(r"(\d+)\s*percent", bat_str)
            if m:
                bat_pct = f"{m.group(1)}%"
            if "on battery" in bat_str:
                power = "Battery"
            elif "charging" in bat_str:
                power = "Charging"

            active_timer = None
            if self.active_timers:
                mins, lbl, st = self.active_timers[-1]
                elapsed = time.time() - st
                rem = max(0, int(mins * 60 - elapsed))
                if rem > 0:
                    active_timer = {"minutes": mins, "label": lbl, "remaining": rem}
                else:
                    self.active_timers = [t for t in self.active_timers if (time.time() - t[2]) < (t[0] * 60)]

            return {
                "status": self.current_status,
                "chip": self.get_chip_name(),
                "cpu": round(psutil.cpu_percent(interval=None)),
                "ram": round(mem.percent),
                "ram_details": f"{used_gb} / {total_gb}.0 GB Unified",
                "battery": bat_pct,
                "power": power,
                "persona": self.persona.upper(),
                "contacts": self.contacts,
                "new_message": self.recent_message,
                "active_timer": active_timer,
                "timestamp": time.time(),
            }
        except Exception:
            return {"status": self.current_status}

    def update_ui_state(self, status, user_speech=None, agent_speech=None, action=None):
        self.current_status = status
        self.last_msg_id += 1
        if user_speech:
            self.recent_message = {"id": self.last_msg_id, "sender": "DEEPAK", "text": user_speech, "type": "user"}
            self.add_log(f"USER: {user_speech}")
        elif agent_speech:
            self.recent_message = {"id": self.last_msg_id, "sender": self.title_name, "text": agent_speech, "type": "agent"}
            self.add_log(f"{self.title_name}: {agent_speech}")
        elif action:
            self.recent_message = {"id": self.last_msg_id, "sender": "ACTION", "text": action, "type": "system"}
            self.add_log(f"ACTION: {action}")

        # Write to state.json as fallback for direct file opening
        try:
            state = self.get_current_state()
            state_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "state.json")
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass

    def launch_hud_interface(self):
        """Launches the interactive Arc Reactor HUD in dedicated Chrome app mode or default browser."""
        target_url = f"http://127.0.0.1:{HUD_PORT}"
        chrome_app = "/Applications/Google Chrome.app"
        if os.path.exists(chrome_app):
            cmd = ["open", "-na", "Google Chrome", "--args", f"--app={target_url}", "--start-fullscreen"]
            subprocess.Popen(cmd)
        else:
            subprocess.Popen(["open", target_url])

    # =========================================================================
    # Voice Output & Audio Feedback
    # =========================================================================
    def speak(self, text):
        clean = re.sub(r"[*_#`~>|]", "", text)
        clean = re.sub(r"\[.*?\]\(.*?\)", "", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        if not clean:
            return

        self.update_ui_state("SPEAKING", agent_speech=clean)
        print(f"\n🤖 {self.title_name}: {clean}\n")
        cmd = ["say", "-r", "175", "-f", "-"]
        if self.voice:
            cmd[1:1] = ["-v", self.voice]
        subprocess.run(cmd, input=clean.encode("utf-8"))
        self.update_ui_state("STANDBY")

    def play_sound(self, sound_type, wait=True):
        sounds = {"start": "Tink", "complete": "Pop", "alert": "Glass", "wake": "Purr", "lock": "Morse"}
        name = sounds.get(sound_type)
        if name:
            sound_path = f"/System/Library/Sounds/{name}.aiff"
            if os.path.exists(sound_path):
                if wait:
                    subprocess.run(["afplay", sound_path])
                else:
                    subprocess.Popen(["afplay", sound_path])

    # =========================================================================
    # Sleep/Wake Watchdog (MacBook Lid Opened Detector)
    # =========================================================================
    def start_wake_watchdog(self):
        if self._watchdog_running:
            return
        self._watchdog_running = True

        def watchdog():
            last_tick = time.time()
            while self._watchdog_running:
                time.sleep(1.0)
                now = time.time()
                elapsed = now - last_tick
                last_tick = now
                if elapsed > 6.0:
                    print("\n⚡ [MacBook lid opened / system wake detected!]")
                    self.update_ui_state("WAKING")
                    self.play_sound("wake", wait=True)
                    chip = self.get_chip_name()
                    bat = self.get_battery_status()
                    self.speak(f"Welcome back, {self.salutation}. All systems nominal on your {chip}. {bat}")

        t = threading.Thread(target=watchdog, daemon=True)
        t.start()

    # =========================================================================
    # Hardware & Telemetry Tools (Apple Silicon M5)
    # =========================================================================
    def get_chip_name(self):
        try:
            chip = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip()
            if chip:
                return chip
        except Exception:
            pass
        return "Apple Silicon"

    def get_battery_status(self):
        try:
            battery = psutil.sensors_battery()
            if battery and battery.percent is not None:
                state = "charging" if battery.power_plugged else "on battery"
                return f"Battery is at {round(battery.percent)} percent, {state}."
        except Exception:
            pass

        try:
            out = subprocess.run(["ioreg", "-rn", "AppleSmartBattery"], capture_output=True, text=True).stdout
            curr_match = re.search(r'"CurrentCapacity"\s*=\s*(\d+)', out)
            max_match = re.search(r'"MaxCapacity"\s*=\s*(\d+)', out)
            is_charging = '"IsCharging" = Yes' in out
            if curr_match:
                curr = int(curr_match.group(1))
                pct = curr
                if max_match and int(max_match.group(1)) > 100:
                    pct = round((curr / int(max_match.group(1))) * 100)

                pmset_out = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True).stdout
                state = "charging" if is_charging else ("on AC power" if "AC Power" in pmset_out else "on battery")
                return f"Battery is at {pct} percent, {state}."
        except Exception:
            pass

        return "Battery status unavailable."

    def tool_system_diagnostics(self):
        chip = self.get_chip_name()
        bat = self.get_battery_status()
        cpu = psutil.cpu_percent(interval=0.3)
        mem = psutil.virtual_memory()
        ram_pct = mem.percent
        used_gb = round(mem.used / (1024**3), 1)
        total_gb = round(mem.total / (1024**3))
        return (f"{chip} architecture. {bat} "
                f"CPU utilization is at {cpu} percent. "
                f"Unified memory load is at {ram_pct} percent, utilizing {used_gb} of {total_gb} gigabytes.")

    def tool_lock_screen(self):
        subprocess.Popen(["pmset", "displaysleepnow"])
        return "Screen locked."

    # =========================================================================
    # Chrome Web Search & Tab Management
    # =========================================================================
    def tool_web_search_browser(self, query, platform="chrome"):
        clean_q = query.strip()
        q_enc = urllib.parse.quote_plus(clean_q)
        plat = platform.lower() if platform else "chrome"

        if plat in ("youtube", "yt"):
            url = f"https://www.youtube.com/results?search_query={q_enc}"
            label = "YouTube"
        elif plat in ("wiki", "wikipedia"):
            url = f"https://en.wikipedia.org/wiki/Special:Search?search={q_enc}"
            label = "Wikipedia"
        elif plat in ("reddit",):
            url = f"https://www.reddit.com/search/?q={q_enc}"
            label = "Reddit"
        elif plat in ("github",):
            url = f"https://github.com/search?q={q_enc}"
            label = "GitHub"
        elif plat in ("amazon",):
            url = f"https://www.amazon.in/s?k={q_enc}"
            label = "Amazon"
        elif plat in ("spotify",):
            url = f"https://open.spotify.com/search/{q_enc}"
            label = "Spotify"
        else:
            url = f"https://www.google.com/search?q={q_enc}"
            label = "Google Chrome"

        chrome_app = "/Applications/Google Chrome.app"
        if os.path.exists(chrome_app):
            subprocess.Popen(["open", "-a", "Google Chrome", url])
        else:
            subprocess.Popen(["open", url])

        self.update_ui_state("STANDBY", action=f"Searched '{clean_q}' on {label}")
        return f"Searching for {clean_q} on {label}."

    def tool_manage_chrome_tabs(self, action):
        if action == "new":
            subprocess.Popen(["open", "-a", "Google Chrome", "https://www.google.com"])
            return "Opened a new tab in Google Chrome."
        elif action == "close":
            script = 'tell application "Google Chrome" to close active tab of front window'
            subprocess.Popen(["osascript", "-e", script])
            return "Closed current tab in Google Chrome."
        elif action == "reload":
            script = 'tell application "Google Chrome" to reload active tab of front window'
            subprocess.Popen(["osascript", "-e", script])
            return "Reloaded current page."
        return "Chrome tab action completed."

    # =========================================================================
    # WhatsApp & Messaging Tools
    # =========================================================================
    def tool_whatsapp_message(self, contact, message):
        clean_msg = message.strip()
        phone = self.resolve_contact_phone(contact) if contact else None

        if phone:
            clean_phone = re.sub(r"[^\d+]", "", phone)
            text_enc = urllib.parse.quote(clean_msg)
            url = f"whatsapp://send?phone={clean_phone}&text={text_enc}"
            subprocess.Popen(["open", url])

            send_script = """
            delay 1.2
            tell application "System Events"
                tell process "WhatsApp"
                    set frontmost to true
                    key code 36
                end tell
            end tell
            """
            subprocess.Popen(["osascript", "-e", send_script])
            self.update_ui_state("STANDBY", action=f"Sent WhatsApp to {contact}: {clean_msg}")
            return f"Sending WhatsApp message to {contact.title()}."

        p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
        p.communicate(input=clean_msg.encode("utf-8"))

        if contact:
            script = f"""
            tell application "WhatsApp" to activate
            delay 0.5
            tell application "System Events"
                tell process "WhatsApp"
                    set frontmost to true
                    keystroke "f" using {{command down}}
                    delay 0.5
                    keystroke "{contact}"
                    delay 0.7
                    key code 36
                    delay 0.5
                    keystroke "v" using {{command down}}
                    delay 0.3
                    key code 36
                end tell
            end tell
            """
            subprocess.Popen(["osascript", "-e", script])
            self.update_ui_state("STANDBY", action=f"Opening WhatsApp for {contact}")
            return f"Opening WhatsApp for {contact.title()} and sending your message."

        subprocess.Popen(["open", "-a", "WhatsApp"])
        return "Opened WhatsApp with your message copied to clipboard."

    def tool_whatsapp_call(self, contact):
        phone = self.resolve_contact_phone(contact)
        if phone:
            clean_phone = re.sub(r"[^\d+]", "", phone)
            subprocess.Popen(["open", f"whatsapp://send?phone={clean_phone}"])

        script = f"""
        tell application "WhatsApp" to activate
        delay 0.5
        tell application "System Events"
            tell process "WhatsApp"
                set frontmost to true
                keystroke "f" using {{command down}}
                delay 0.4
                keystroke "{contact}"
                delay 0.6
                key code 36
                delay 0.5
                try
                    click (first button whose description contains "Audio" or description contains "Call" or help contains "Call")
                end try
            end tell
        end tell
        """
        subprocess.Popen(["osascript", "-e", script])
        self.update_ui_state("STANDBY", action=f"Calling {contact} on WhatsApp")
        return f"Initiating WhatsApp call to {contact.title()}."

    def tool_instagram_message(self, username, message=None):
        clean_user = username.lstrip("@").strip() if username else None

        if clean_user:
            url = f"https://www.instagram.com/direct/t/{clean_user}/"
            if message:
                p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
                p.communicate(input=message.encode("utf-8"))

            if os.path.exists("/Applications/Google Chrome.app"):
                subprocess.Popen(["open", "-a", "Google Chrome", url])
            else:
                subprocess.Popen(["open", url])

            label = f"to @{clean_user}"
            if message:
                label += " with message on clipboard"
            self.update_ui_state("STANDBY", action=f"Opened Instagram DM with @{clean_user}")
            return f"Opening Instagram direct message {label}."
        else:
            url = "https://www.instagram.com/direct/inbox/"
            if os.path.exists("/Applications/Google Chrome.app"):
                subprocess.Popen(["open", "-a", "Google Chrome", url])
            else:
                subprocess.Popen(["open", url])
            self.update_ui_state("STANDBY", action="Opened Instagram Inbox")
            return "Opening Instagram Direct Inbox."

    def tool_phone_or_facetime_call(self, contact):
        phone = self.resolve_contact_phone(contact)
        target = phone if phone else contact
        clean_target = re.sub(r"[^\d+]", "", target)
        if clean_target and len(clean_target) >= 7:
            subprocess.Popen(["open", f"tel:{clean_target}"])
            return f"Calling {contact.title()} at {clean_target}."
        else:
            subprocess.Popen(["open", f"facetime:{target}"])
            return f"Calling {contact.title()} via FaceTime."

    # =========================================================================
    # macOS Application & Web Tools
    # =========================================================================
    def find_installed_apps(self):
        app_dirs = [
            "/Applications",
            "/System/Applications",
            "/System/Applications/Utilities",
            os.path.expanduser("~/Applications")
        ]
        apps = {}
        for d in app_dirs:
            if os.path.exists(d):
                for item in os.listdir(d):
                    if item.endswith(".app"):
                        name = item[:-4]
                        apps[name.lower()] = (name, os.path.join(d, item))
        if "bionic" in apps:
            apps["lm studio"] = ("LM Studio", apps["bionic"][1])
            apps["lmstudio"] = ("LM Studio", apps["bionic"][1])
            apps["nemotron"] = ("LM Studio", apps["bionic"][1])
        return apps

    def tool_open_app(self, app_name):
        target = APP_ALIASES.get(app_name.lower().strip(), app_name.lower().strip())
        installed = self.find_installed_apps()
        app_match = installed.get(target)
        if not app_match:
            matches = [v for k, v in installed.items() if target in k or k in target]
            if matches:
                app_match = matches[0]

        if app_match:
            display_name, app_path = app_match
            subprocess.Popen(["open", app_path])
            self.update_ui_state("STANDBY", action=f"Launched {display_name}")
            return f"Successfully launched {display_name}."
        else:
            subprocess.Popen(["open", "-a", app_name])
            self.update_ui_state("STANDBY", action=f"Launched {app_name}")
            return f"Requested macOS to launch {app_name}."

    def tool_close_app(self, app_name):
        target = APP_ALIASES.get(app_name.lower().strip(), app_name.lower().strip())
        installed = self.find_installed_apps()
        app_match = installed.get(target) or ([v for k, v in installed.items() if target in k or k in target] or [None])[0]
        display_name = app_match[0] if app_match else app_name
        subprocess.Popen(["osascript", "-e", f'tell application "{display_name}" to quit'])
        self.update_ui_state("STANDBY", action=f"Closed {display_name}")
        return f"Closed application {display_name}."

    def tool_open_website(self, url, site_name=None):
        destination = WEBSITES.get(url.lower().strip(), url)
        if not destination.startswith("http"):
            destination = f"https://{destination}"
        subprocess.Popen(["open", destination])
        label = site_name or url
        self.update_ui_state("STANDBY", action=f"Opened {label}")
        return f"Opened {label} in your default browser."

    def tool_control_volume(self, action, level=None):
        if action == "mute":
            subprocess.Popen(["osascript", "-e", "set volume output muted true"])
            return "System audio muted."
        elif action == "unmute":
            subprocess.Popen(["osascript", "-e", "set volume output muted false"])
            return "System audio unmuted."
        elif action == "up":
            subprocess.Popen(["osascript", "-e", "set volume output volume 80"])
            return "Volume raised to 80 percent."
        elif action == "down":
            subprocess.Popen(["osascript", "-e", "set volume output volume 40"])
            return "Volume lowered to 40 percent."
        elif action == "set" and level is not None:
            pct = max(0, min(100, int(level)))
            subprocess.Popen(["osascript", "-e", f"set volume output volume {pct}"])
            return f"Volume set to {pct} percent."
        return "Volume adjustment executed."

    def tool_take_screenshot(self):
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.expanduser(f"~/Desktop/Screenshot_{ts}.png")
        subprocess.Popen(["screencapture", path])
        self.update_ui_state("STANDBY", action="Screenshot saved to Desktop")
        return "Screenshot captured and saved to your Desktop."

    # =========================================================================
    # Notes, Timers & Weather Tools
    # =========================================================================
    def tool_get_weather(self, location="Gurugram"):
        loc = location or "Gurugram"
        try:
            r = requests.get(f"https://wttr.in/{requests.utils.quote(loc)}?format=3", timeout=5)
            if r.status_code == 200 and r.text.strip():
                return f"Weather report for {loc}: {r.text.strip()}"
        except Exception:
            pass
        return f"Weather information is currently unavailable for {loc}."

    def tool_set_timer(self, minutes, label="timer"):
        duration_sec = int(float(minutes) * 60)

        def worker():
            time.sleep(duration_sec)
            self.play_sound("alert", wait=True)
            self.speak(f"{self.salutation}, your {label} of {minutes} minute{'s' if minutes != 1 else ''} has finished.")

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        self.active_timers.append((minutes, label, time.time()))
        return f"Started a {minutes} minute timer for {label}."

    def tool_take_note(self, title, content):
        notes_dir = "/Users/deepaksiwach/Documents/JarvisNotes" if os.path.isdir("/Users/deepaksiwach/Documents") else os.path.expanduser("~/Documents/JarvisNotes")
        os.makedirs(notes_dir, exist_ok=True)
        safe_title = re.sub(r"[^a-zA-Z0-9_-]", "_", title).strip("_") or "note"
        filepath = os.path.join(notes_dir, f"{safe_title}.txt")
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {title}\n{content}\n\n")
        return f"Note recorded to Documents/JarvisNotes/{safe_title}.txt."

    def get_all_notes(self):
        notes_dir = "/Users/deepaksiwach/Documents/JarvisNotes" if os.path.isdir("/Users/deepaksiwach/Documents") else os.path.expanduser("~/Documents/JarvisNotes")
        os.makedirs(notes_dir, exist_ok=True)
        notes = []
        for fname in os.listdir(notes_dir):
            if fname.endswith(".txt"):
                fpath = os.path.join(notes_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        content = f.read()
                    mtime = os.path.getmtime(fpath)
                    notes.append({
                        "filename": fname,
                        "title": fname[:-4].replace("_", " "),
                        "content": content,
                        "date": time.strftime("%b %d, %Y %I:%M %p", time.localtime(mtime))
                    })
                except Exception:
                    pass
        return sorted(notes, key=lambda x: x["filename"])

    def delete_note(self, filename):
        notes_dir = "/Users/deepaksiwach/Documents/JarvisNotes" if os.path.isdir("/Users/deepaksiwach/Documents") else os.path.expanduser("~/Documents/JarvisNotes")
        safe_name = os.path.basename(filename)
        if not safe_name.endswith(".txt"):
            safe_name += ".txt"
        fpath = os.path.join(notes_dir, safe_name)
        if os.path.exists(fpath):
            os.remove(fpath)
            return True
        return False

    def delete_contact(self, name):
        clean_name = name.lower().strip()
        if clean_name in self.contacts:
            del self.contacts[clean_name]
            self.save_contacts()
            return True
        return False

    # =========================================================================
    # Agent Tool Dispatcher
    # =========================================================================
    def execute_tool(self, name, args):
        print(f"⚙️ Agent Action: {name}({args})")
        self.update_ui_state("THINKING", action=f"Action: {name}")

        if name == "search_web_in_browser":
            return self.tool_web_search_browser(args.get("query", ""), args.get("platform", "chrome"))
        elif name == "send_whatsapp_message":
            return self.tool_whatsapp_message(args.get("contact", ""), args.get("message", ""))
        elif name == "make_whatsapp_call":
            return self.tool_whatsapp_call(args.get("contact", ""))
        elif name == "send_instagram_message":
            return self.tool_instagram_message(args.get("username", ""), args.get("message", ""))
        elif name == "manage_chrome_tabs":
            return self.tool_manage_chrome_tabs(args.get("action", "new"))
        elif name == "open_application":
            return self.tool_open_app(args.get("app_name", ""))
        elif name == "close_application":
            return self.tool_close_app(args.get("app_name", ""))
        elif name == "system_diagnostics":
            return self.tool_system_diagnostics()
        elif name == "take_screenshot":
            return self.tool_take_screenshot()
        elif name == "save_contact":
            return self.tool_save_contact(args.get("name", ""), args.get("phone", ""))
        elif name == "control_volume":
            return self.tool_control_volume(args.get("action", ""), args.get("level"))
        elif name == "get_weather":
            return self.tool_get_weather(args.get("location", "Gurugram"))
        elif name == "set_timer":
            return self.tool_set_timer(args.get("minutes", 1), args.get("label", "timer"))
        elif name == "take_note":
            return self.tool_take_note(args.get("title", "Note"), args.get("content", ""))
        return f"Unknown tool: {name}"

    # =========================================================================
    # Intent Matchers (Zero-Latency Fast Interceptors)
    # =========================================================================
    def parse_search_intent(self, query):
        clean = re.sub(r"^(hey\s+)?(jarvis|friday)\s*,?\s*", "", query, flags=re.I).strip()
        clean = re.sub(r"^(can\s+you|could\s+you|please|would\s+you)\s+", "", clean, flags=re.I).strip()

        m1 = re.search(r"\b(?:search|look\s+up|find)\s+(?:for\s+)?(.+?)\s+(?:on|in)\s+(chrome|google|youtube|wikipedia|wiki|reddit|github|amazon|spotify)\b", clean, re.I)
        if m1:
            return m1.group(1).strip(), m1.group(2).lower().strip()

        m2 = re.search(r"\b(?:search|look\s+up|find\s+in)\s+(chrome|google|youtube|wikipedia|wiki|reddit|github|amazon|spotify)\s+(?:for\s+)?(.+)", clean, re.I)
        if m2:
            return m2.group(2).strip(), m2.group(1).lower().strip()

        m3 = re.search(r"\b(?:google)\s+(.+)", clean, re.I)
        if m3:
            return m3.group(1).strip(), "google"

        m4 = re.search(r"\b(?:play)\s+(.+?)(?:\s+(?:on|in)\s+(youtube|spotify))?$", clean, re.I)
        if m4:
            plat = m4.group(2).lower() if m4.group(2) else "youtube"
            return m4.group(1).strip(), plat

        m5 = re.search(r"\b(?:search\s+for|search)\s+(.+)", clean, re.I)
        if m5 and not any(w in clean.lower() for w in ["whatsapp", "contacts", "devices", "instagram", "ig"]):
            return m5.group(1).strip(), "chrome"

        return None, None

    def parse_comm_intent(self, query):
        clean = re.sub(r"^(hey\s+)?(jarvis|friday)\s*,?\s*", "", query, flags=re.I).strip()
        clean = re.sub(r"^(can\s+you|could\s+you|please|would\s+you)\s+", "", clean, flags=re.I).strip()

        m_ig_inbox = re.search(r"\b(?:open|check)\s+(?:instagram|ig)\s+(?:dm|dms|messages|inbox)\b", clean, re.I)
        if m_ig_inbox:
            return "ig_inbox", None, None

        m_ig_call = re.search(r"\b(?:call|video\s+call)\s+(@?[\w\.]+)\s+(?:on|via)\s+(?:instagram|ig)\b", clean, re.I)
        if m_ig_call:
            return "ig_call", m_ig_call.group(1).lstrip("@"), None

        m_ig_1 = re.search(r"\b(?:send\s+(?:a\s+)?(?:message|dm)\s+(?:on|via)\s+(?:instagram|ig)\s+to|send\s+(?:@?[\w\.]+)\s+(?:a\s+)?(?:message|dm)\s+(?:on|via)\s+(?:instagram|ig))\s*(@?[\w\.]+)?\s*(?:saying|that|with\s+message|:)?\s*(.+)?", clean, re.I)
        if m_ig_1:
            u = m_ig_1.group(1) or ""
            m = m_ig_1.group(2) or ""
            return "ig_msg", u.lstrip("@"), m.strip()

        m_ig_2 = re.search(r"\b(?:dm|message)\s+(@?[\w\.]+)\s+(?:on|via)\s+(?:instagram|ig)\s*(?:saying|that|with\s+message|:)?\s*(.+)?", clean, re.I)
        if m_ig_2:
            return "ig_msg", m_ig_2.group(1).lstrip("@"), (m_ig_2.group(2) or "").strip()

        m_wa_call = re.search(r"\b(?:call|make\s+a\s+call\s+to|voice\s+call)\s+(.+?)(?:\s+(?:on|via)\s+whatsapp)\b", clean, re.I)
        if not m_wa_call:
            m_wa_call = re.search(r"\bwhatsapp\s+call\s+(.+)", clean, re.I)
        if m_wa_call:
            return "wa_call", m_wa_call.group(1).strip(), None

        m_wa_1 = re.search(r"\b(?:send\s+(?:a\s+)?message\s+to\s+(.+?)\s+(?:on|via)\s+whatsapp|send\s+(?:a\s+)?message\s+(?:on|via)\s+whatsapp\s+to\s+(.+?)|message\s+(.+?)\s+(?:on|via)\s+whatsapp|text\s+(.+?)\s+(?:on|via)\s+whatsapp|whatsapp\s+(.+?))\s+(?:saying|that|with\s+message|:)\s+(.+)", clean, re.I)
        if m_wa_1:
            contact = m_wa_1.group(1) or m_wa_1.group(2) or m_wa_1.group(3) or m_wa_1.group(4) or m_wa_1.group(5)
            msg = m_wa_1.group(6)
            return "wa_msg", contact.strip(), msg.strip()

        m_wa_2 = re.search(r"\b(?:send\s+(?:a\s+)?message\s+(?:on|via)\s+whatsapp|whatsapp\s+message|send\s+whatsapp)\s+(?:saying|:)?\s*(.+)", clean, re.I)
        if m_wa_2:
            return "wa_msg", None, m_wa_2.group(1).strip()

        m_call = re.search(r"\b(?:call|phone|facetime)\s+(.+?)(?:\s+please)?$", clean, re.I)
        if m_call and not any(w in clean.lower() for w in ["diagnostics", "system", "status", "off", "whatsapp", "instagram", "ig"]):
            return "phone_call", m_call.group(1).strip(), None

        return None, None, None

    def fast_intent_router(self, query):
        raw_clean = re.sub(r"[^\w\s]", "", query.lower()).strip()
        s = self.salutation

        # 0. Direct Wake Word Invocation (Like Siri: "Hey Jarvis" -> "Yes, Sir?")
        if raw_clean in ("hey jarvis", "jarvis", "hey friday", "friday", "ok jarvis", "ok friday", "wake up", "are you there", "you there"):
            self.play_sound("wake", wait=False)
            reply = f"Yes, {s}? Online and listening."
            self.speak(reply)
            return True

        clean = re.sub(r"[^\w\s]", "", query.lower()).strip()
        clean = re.sub(r"^(hey\s+)?(jarvis|friday)\s*,?\s*", "", clean)
        clean = re.sub(r"^(can\s+you|could\s+you|please|would\s+you)\s+", "", clean)

        # 1. Direct Search on Chrome / YouTube / Web
        search_term, search_plat = self.parse_search_intent(query)
        if search_term and search_plat:
            res = self.tool_web_search_browser(search_term, search_plat)
            self.speak(f"{res.rstrip('.')}, {s}.")
            return True

        # 2. WhatsApp & Instagram Messaging and Calling
        comm_act, comm_target, comm_content = self.parse_comm_intent(query)
        if comm_act == "wa_msg":
            res = self.tool_whatsapp_message(comm_target, comm_content)
            self.speak(f"{res.rstrip('.')}, {s}.")
            return True
        elif comm_act == "wa_call":
            res = self.tool_whatsapp_call(comm_target)
            self.speak(f"{res.rstrip('.')}, {s}.")
            return True
        elif comm_act == "ig_msg":
            res = self.tool_instagram_message(comm_target, comm_content)
            self.speak(f"{res.rstrip('.')}, {s}.")
            return True
        elif comm_act == "ig_inbox":
            res = self.tool_instagram_message(None)
            self.speak(f"{res.rstrip('.')}, {s}.")
            return True
        elif comm_act == "ig_call":
            res = self.tool_instagram_message(comm_target)
            self.speak(f"Opening Instagram direct thread with @{comm_target} for your call, {s}.")
            return True
        elif comm_act == "phone_call":
            res = self.tool_phone_or_facetime_call(comm_target)
            self.speak(f"{res.rstrip('.')}, {s}.")
            return True

        # 3. Chrome Tab Management
        if has(clean, "new tab", "open a new tab", "open new tab"):
            res = self.tool_manage_chrome_tabs("new")
            self.speak(f"{res.rstrip('.')}, {s}.")
            return True
        if has(clean, "close tab", "close current tab"):
            res = self.tool_manage_chrome_tabs("close")
            self.speak(f"{res.rstrip('.')}, {s}.")
            return True
        if has(clean, "reload tab", "reload page", "refresh page"):
            res = self.tool_manage_chrome_tabs("reload")
            self.speak(f"{res.rstrip('.')}, {s}.")
            return True

        # 4. Screenshot
        if has(clean, "take a screenshot", "screenshot", "capture screen"):
            res = self.tool_take_screenshot()
            self.speak(f"{res.rstrip('.')}, {s}.")
            return True

        # 5. Contact Saving ("save contact Dad: 9812345678")
        save_m = re.search(r"\b(?:save\s+contact|add\s+contact)\s+(.+?)(?:\s+(?:as|with\s+number|:))?\s+(\+?\d[\d\s\-]{6,15})", query, re.I)
        if save_m:
            c_name = save_m.group(1).strip()
            c_phone = save_m.group(2).strip()
            res = self.tool_save_contact(c_name, c_phone)
            self.speak(f"{res.rstrip('.')}, {s}.")
            return True

        # 6. Screen Lock
        if has(clean, "lock screen", "lock my screen", "lock display", "sleep screen"):
            self.play_sound("lock", wait=False)
            self.tool_lock_screen()
            self.speak(f"Screen locked, {s}.")
            return True

        # 7. System Diagnostics
        if has(clean, "system status", "diagnostics", "telemetry", "hardware status", "specs"):
            self.speak(f"Running full diagnostics, {s}. {self.tool_system_diagnostics()}")
            return True

        # 8. Volume Controls
        vol_m = re.search(r"\b(?:set\s+)?volume\s+(?:to\s+)?(\d{1,3})(?:\s*%)?", clean)
        if vol_m:
            lvl = max(0, min(100, int(vol_m.group(1))))
            self.tool_control_volume("set", lvl)
            self.speak(f"Setting audio output to {lvl} percent, {s}.")
            return True
        if has(clean, "unmute"):
            self.tool_control_volume("unmute")
            self.speak(f"Audio restored, {s}.")
            return True
        if has(clean, "mute"):
            self.tool_control_volume("mute")
            print(f"🔇 Audio muted, {s}.")
            return True
        if has(clean, "max volume", "volume up"):
            self.tool_control_volume("up")
            self.speak(f"Adjusting audio output to 80 percent, {s}.")
            return True
        if has(clean, "volume down"):
            self.tool_control_volume("down")
            self.speak(f"Lowering audio output to 40 percent, {s}.")
            return True

        # 9. Close / Quit Application
        close_m = re.search(r"\b(?:close|quit|exit|terminate|kill)\s+(?:the\s+)?(.+)", clean)
        if close_m:
            target = close_m.group(1).strip()
            for suffix in [" please", " app", " application", " browser", " sir", " boss", " for me"]:
                if target.endswith(suffix):
                    target = target[:-len(suffix)].strip()
            res = self.tool_close_app(target)
            self.speak(f"{res.rstrip('.')}, {s}.")
            return True

        # 10. Open / Launch Application or Website
        open_m = re.search(r"\b(?:open|launch|start|run|bring up|activate|switch to)\s+(?:the\s+)?(.+)", clean)
        if open_m:
            target = open_m.group(1).strip()
            for suffix in [" please", " app", " application", " browser", " sir", " boss", " for me"]:
                if target.endswith(suffix):
                    target = target[:-len(suffix)].strip()

            if target in WEBSITES:
                self.tool_open_website(WEBSITES[target], target.title())
                self.speak(f"Opening {target.title()}, {s}.")
                return True

            target_app = APP_ALIASES.get(target, target)
            installed = self.find_installed_apps()
            app_match = installed.get(target_app) or ([v for k, v in installed.items() if target_app in k or k in target_app] or [None])[0]

            if app_match:
                display_name, app_path = app_match
                subprocess.Popen(["open", app_path])
                self.speak(f"Opening {display_name}, {s}.")
                return True
            elif "." in target or "http" in target:
                self.tool_open_website(target)
                self.speak(f"Navigating to {target}, {s}.")
                return True

        # 11. Study & Countdown Timers
        timer_m = re.search(r"\b(?:set\s+a?\s*timer|timer)\s+(?:for\s+)?(\d+(?:\.\d+)?)\s*(?:minutes?|mins?)(?:\s+(?:for|to)\s+(.+))?", clean)
        if timer_m:
            mins = float(timer_m.group(1))
            lbl = timer_m.group(2).strip() if timer_m.group(2) else "study session"
            res = self.tool_set_timer(mins, lbl)
            self.speak(f"{res.rstrip('.')}, {s}.")
            return True

        # 12. Notes & Memos Recording
        note_m = re.search(r"\b(?:take\s+a?\s*note|save\s+note|remember|write\s+down)\s+(?:about\s+|that\s+)?(.+)", query, re.I)
        if note_m:
            body = note_m.group(1).strip()
            title = "Quick Note"
            if ":" in body:
                parts = body.split(":", 1)
                title, body = parts[0].strip(), parts[1].strip()
            res = self.tool_take_note(title, body)
            self.speak(f"{res.rstrip('.')}, {s}.")
            return True

        return False

    # =========================================================================
    # LM Studio (Nemotron) & Local AI Reasoning Loop
    # =========================================================================
    def ensure_local_engine(self):
        eng = self.get_active_engine_info()
        return eng["active"]

    def agentic_reasoning_loop(self, user_query):
        self.history.append({"role": "user", "content": user_query})
        self.history = self.history[-MAX_HISTORY_TURNS * 2:]

        eng_info = self.get_active_engine_info()
        messages = [{"role": "system", "content": self.system_prompt}] + self.history

        # 1. LM Studio is Active (Nemotron)
        if eng_info["type"] == "lm_studio":
            try:
                print(f"⚡ Thinking with LM Studio [{eng_info['model']}]...")
                self.update_ui_state("THINKING")
                payload = {
                    "model": eng_info["model"],
                    "messages": messages,
                    "temperature": 0.5,
                    "max_tokens": 250,
                    "stream": False,
                    "tools": OLLAMA_TOOLS
                }
                r = requests.post(f"{LM_STUDIO_URL}/chat/completions", json=payload, timeout=90)
                r.raise_for_status()
                resp_json = r.json()
                choices = resp_json.get("choices", [])
                if choices:
                    res_msg = choices[0].get("message", {})
                    tool_calls = res_msg.get("tool_calls", [])
                    if tool_calls:
                        for tc in tool_calls:
                            fn = tc.get("function", {})
                            fn_name = fn.get("name")
                            fn_args_raw = fn.get("arguments", "{}")
                            if isinstance(fn_args_raw, str):
                                try:
                                    fn_args = json.loads(fn_args_raw)
                                except Exception:
                                    fn_args = {}
                            else:
                                fn_args = fn_args_raw
                            self.play_sound("wake", wait=False)
                            tool_output = self.execute_tool(fn_name, fn_args)
                            messages.append(res_msg)
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc.get("id", "call_1"),
                                "content": str(tool_output)
                            })

                        payload["messages"] = messages
                        payload.pop("tools", None)
                        r2 = requests.post(f"{LM_STUDIO_URL}/chat/completions", json=payload, timeout=60)
                        r2.raise_for_status()
                        choice2 = r2.json().get("choices", [{}])[0]
                        final_text = choice2.get("message", {}).get("content", "").strip()
                    else:
                        final_text = res_msg.get("content", "").strip()

                    self.history.append({"role": "assistant", "content": final_text})
                    return final_text
            except Exception as e:
                self.add_log(f"LM Studio query failed: {e}")

        # 2. Ollama Fallback
        elif eng_info["type"] == "ollama":
            try:
                print("⚡ Thinking with Ollama...")
                self.update_ui_state("THINKING")
                payload = {
                    "model": "llama3.2",
                    "stream": False,
                    "keep_alive": "30m",
                    "messages": messages,
                    "tools": OLLAMA_TOOLS,
                    "options": {"num_predict": 150, "temperature": 0.5},
                }
                r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=90)
                r.raise_for_status()
                res_msg = r.json().get("message", {})
                tool_calls = res_msg.get("tool_calls", [])
                if tool_calls:
                    for tc in tool_calls:
                        fn = tc.get("function", {})
                        fn_name = fn.get("name")
                        fn_args = fn.get("arguments", {})
                        self.play_sound("wake", wait=False)
                        tool_output = self.execute_tool(fn_name, fn_args)
                        messages.append(res_msg)
                        messages.append({"role": "tool", "content": str(tool_output)})
                    payload["messages"] = messages
                    payload.pop("tools", None)
                    r2 = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=60)
                    r2.raise_for_status()
                    final_text = r2.json().get("message", {}).get("content", "").strip()
                else:
                    final_text = res_msg.get("content", "").strip()

                self.history.append({"role": "assistant", "content": final_text})
                return final_text
            except Exception as e:
                self.add_log(f"Ollama query failed: {e}")

        # 3. Offline
        self.history.pop()
        return f"Sir, my reasoning core is set to LM Studio with Nemotron, but the local server on port 1234 is currently offline. Please open LM Studio and start the local server to enable full conversational intelligence."

    # =========================================================================
    # Audio Capture & Voice Loop
    # =========================================================================
    def calibrate_microphone(self):
        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
            self.has_microphone = True
            print("🎙️ Microphone successfully calibrated and ready.")
            return True
        except Exception as e:
            print(f"[Notice: System microphone input unavailable: {e}]")
            print("         (Interactive Mission Control HUD and typed/touch commands remain 100% operational)")
            self.has_microphone = False
            return False
    def listen_microphone(self):
        try:
            with sr.Microphone() as source:
                self.update_ui_state("LISTENING")
                self.play_sound("start", wait=True)
                print("🎙️ Listening...")
                audio = self.recognizer.listen(source, timeout=6, phrase_time_limit=12)
                text = self.recognizer.recognize_google(audio)
                print(f"👤 You: {text}")
                self.update_ui_state("THINKING", user_speech=text)
                return text
        except (sr.WaitTimeoutError, sr.UnknownValueError):
            self.update_ui_state("STANDBY")
            return ""
        except sr.RequestError:
            print("[Speech recognition network service unreachable - check internet connection]")
            self.update_ui_state("STANDBY")
            time.sleep(2)
            return ""
        except Exception as e:
            print(f"[Microphone error: {e}]")
            self.has_microphone = False
            self.update_ui_state("STANDBY")
            return ""
    def run(self):
        print("c", end="")
        chip = self.get_chip_name()
        print("=========================================================")
        print(f"   {self.title_name} AUTONOMOUS MISSION CONTROL - {chip.upper()}   ")
        print("=========================================================")
        print("   Capabilities: Full Interactive Arc Reactor Dashboard,  ")
        print("                 WhatsApp Messages/Calls, Instagram DMs,  ")
        print("                 Chrome Searches, Tabs, Timers, Telemetry ")
        print("=========================================================")

        # Start the embedded HTTP server for interactive GUI controls
        self.start_http_server()

        if self.use_gui:
            print("🚀 Launching J.A.R.V.I.S. Interactive Mission Control HUD...")
            self.launch_hud_interface()

        # Check microphone without exiting on failure
        self.calibrate_microphone()

        eng = self.get_active_engine_info()
        if eng["active"]:
            print(f"🤖 Local AI Core Online: {eng['engine']} — Model: {eng['model']}")
        else:
            print(f"⚡ Local AI Core Status: {eng['engine']} ({eng['model']}). Open LM Studio on port 1234 for Nemotron reasoning.")

        self.start_wake_watchdog()
        self.speak(f"{self.title_name} system online on your {chip}. How may I assist you today, {self.salutation}?")

        try:
            while True:
                if not self.use_gui and self.has_microphone:
                    # Headless CLI Mode only: listen to microphone from terminal
                    query = self.listen_microphone()
                    if not query:
                        continue

                    if has(query.lower(), "exit", "shutdown", "goodbye", "quit", "power down"):
                        self.speak(f"Powering down systems. Have a productive study session, {self.salutation}.")
                        break

                    self.process_input_command(query)
                else:
                    # Unified App Mode: The backend engine serves all processing requests from the interface
                    time.sleep(0.5)

        except KeyboardInterrupt:
            print("\nShutting down.")
        finally:
            self._watchdog_running = False
            if self._ollama_proc:
                self._ollama_proc.terminate()


if __name__ == "__main__":
    persona = "jarvis"
    cli_mode = False
    args = [a.lower() for a in sys.argv[1:]]
    if "friday" in args:
        persona = "friday"
    if "--cli" in args:
        cli_mode = True

    VoiceAgent(persona=persona, use_gui=not cli_mode).run()
