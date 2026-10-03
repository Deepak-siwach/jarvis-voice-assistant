# J.A.R.V.I.S. / F.R.I.D.A.Y. Autonomous Voice AI Agent for macOS

An autonomous butler and tactical voice assistant for macOS, powered locally by **LM Studio** (**NVIDIA Nemotron**) and native Apple Silicon system telemetry.

Featuring a 60 FPS holographic Arc Reactor HUD, hands-free Siri-style wake word detection, ambient conversation filtering, and deep macOS automation.

---

## ⚡ Key Highlights

### 1. Hands-Free Wake Word (Siri-Mode)
- Say **"Hey Jarvis"** (or *"Jarvis"*, *"Friday"*) to wake up the assistant.
- Plays an audio wake chime, pulses the Arc Reactor HUD to active cyan (`WAKING / LISTENING`), and responds: *"Yes, Sir? Online and listening."*
- Supports both separate wake-and-command interactions or single-phrase execution: *"Hey Jarvis, open VS Code"*.

### 2. Conversational Intentionality Gatekeeper (Zero Dumb Replies)
- Detects ambient speech when talking to family (*Mom*, *Dad*) or friends/roommates (*Rahul*, *bro*, *bhai*).
- If speech is not explicitly addressed to Jarvis, the assistant remains **completely silent**—preventing awkward or irrelevant interruptions during personal conversations.

### 3. Local Neural Intelligence (LM Studio + Nemotron)
- Operates locally with **LM Studio** running the **NVIDIA Nemotron-3-Nano** model via an OpenAI-compatible REST server (`http://127.0.0.1:1234/v1`).
- Native function calling allows Nemotron to autonomously trigger browser searches, communications, and desktop utilities.
- Graceful offline fallback with system notifications if the local server is paused.

### 4. Direct macOS Automation & Academic Tools
- **Chrome & Web Searches:** Open instant queries in Google Chrome (*"search manga on chrome"*, *"play lofi beats on youtube"*, *"search python on reddit"*).
- **Academic Portals:** One-tap and voice access to IIT Patna Moodle, Microsoft Webmail, and university portals.
- **Desktop Communications:** Voice-triggered WhatsApp messaging, WhatsApp calls, and FaceTime.
- **System Utilities:** Screenshots saved to Desktop, screen lock, Spotify/Apple Music media controls, countdown study timers, and quick markdown notes.

### 5. Arc Reactor Holographic HUD
- Interactive multi-view dashboard:
  - **Mission Control Overview:** 60 FPS Canvas Arc Reactor with audio wave visualizer and real-time Apple Silicon CPU/RAM/Battery metrics.
  - **All Apps Grid:** Instant search and launch for all installed macOS applications.
  - **Communications Hub:** Speed-dial contacts and WhatsApp messaging.
  - **IITP Study Hub:** Academic links and study session timers.
  - **Notes & Memos:** Live markdown notepad stored locally in `~/Documents/JarvisNotes`.
  - **Backend & Terminal Supervisor:** Live log stream and sandboxed macOS bash terminal runner.

---

## 🛠️ Architecture

```
┌────────────────────────────────────────────────────────┐
│                   Mission Control HUD                  │
│       (Chromium Standalone Window / 60 FPS Canvas)     │
└──────────────▲──────────────────────────▲──────────────┘
               │ Web Speech API (Wake)    │ WebSocket / HTTP
               ▼                          ▼
┌────────────────────────────────────────────────────────┐
│                   jarvis.py Backend                    │
│            Embedded Local Server (Port 8765)           │
├────────────────────────────────────────────────────────┤
│ • Intentionality & Directed-Speech Gatekeeper          │
│ • Sub-10ms Regex Fast Intent Router                   │
│ • AppleScript & macOS System Tool Executor             │
└──────────────▲──────────────────────────▲──────────────┘
               │                          │
               ▼                          ▼
┌───────────────────────────┐ ┌──────────────────────────┐
│   LM Studio (Nemotron)    │ │   macOS CoreAudio / say  │
│   OpenAI API (Port 1234)  │ │   Daniel / Moira Voices  │
└───────────────────────────┘ └──────────────────────────┘
```

---

## 🚀 Getting Started

### Prerequisites
1. **macOS** (Optimized for Apple Silicon M-series).
2. **Python 3.10+**.
3. **Google Chrome** (for optimal Web Speech recognition).
4. **LM Studio** with **NVIDIA Nemotron** (or any GGUF model) loaded on port `1234`.

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/<your-username>/jarvis-voice-assistant.git
   cd jarvis-voice-assistant
   ```

2. **Set up the virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure contacts (Optional):**
   ```bash
   cp contacts.example.json contacts.json
   # Add your phone numbers or nicknames in contacts.json
   ```

4. **Launch Jarvis:**
   ```bash
   ./run.sh
   ```
   *(or double-click **JARVIS.app** on macOS)*

---

## 🎙️ Spoken Command Examples

| Spoken Command | Action Executed |
| :--- | :--- |
| *"Hey Jarvis"* | Wakes assistant, plays chime, prompts *"Yes, Sir?"* |
| *"Hey Jarvis, search manga on Chrome"* | Opens new Google Chrome tab with manga results |
| *"Hey Jarvis, open Moodle"* | Opens IIT Patna Moodle academic portal |
| *"Hey Jarvis, open Webmail"* | Opens Outlook Office 365 portal |
| *"Hey Jarvis, send a message on WhatsApp to Mom saying I'm coming home"* | Pre-fills and sends WhatsApp message |
| *"Hey Jarvis, take a screenshot"* | Captures screen to Desktop PNG |
| *"Hey Jarvis, lock my screen"* | Puts display to sleep immediately |
| *"Hey Jarvis, set a timer for 25 minutes for study session"* | Starts background countdown with chime |
| *"Hey Jarvis, take a note: review asymmetric cryptography"* | Saves timestamped note to `~/Documents/JarvisNotes` |
| *"Hey Jarvis, system diagnostics"* | Audibly reports CPU load, RAM usage, and battery |

---

## 🔒 Privacy & Safety

- **100% Local Inference:** All language reasoning runs locally on your machine via LM Studio; no proprietary conversation data is sent to third-party cloud providers.
- **Family & Personal Boundary Guard:** Passive listening filters out conversation directed at family members or friends.
- **Private Data Excluded:** User notes, personal logs, and `contacts.json` are excluded via `.gitignore`.

---

## 📄 License
MIT License. Created by Deepak Siwach.
