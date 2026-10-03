#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "================================================="
echo "   J.A.R.V.I.S. / F.R.I.D.A.Y. Mac Setup Script  "
echo "        Optimized for MacBook Air (Apple M5)     "
echo "================================================="

if [ "$(uname -s)" != "Darwin" ]; then
    echo "[!] This script is for macOS only."
    exit 1
fi

# Ensure Homebrew environment on Apple Silicon
if [ -x /opt/homebrew/bin/brew ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
elif ! command -v brew &> /dev/null; then
    echo "[!] Homebrew not found. Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv)"
fi

echo "[+] Verifying PortAudio and Ollama via Homebrew..."
brew install portaudio ollama

# Choose best Python 3 interpreter (prefer Homebrew's modern Python on Apple Silicon)
if [ -x /opt/homebrew/bin/python3 ]; then
    PYTHON_CMD="/opt/homebrew/bin/python3"
else
    PYTHON_CMD="python3"
fi

echo "[+] Creating Python virtual environment using $PYTHON_CMD..."
"$PYTHON_CMD" -m venv --system-site-packages .venv
source .venv/bin/activate
pip install --upgrade pip

echo "[+] Installing and verifying Python dependencies for Apple Silicon..."
BREW_PREFIX="$(brew --prefix)"
CFLAGS="-I${BREW_PREFIX}/include" LDFLAGS="-L${BREW_PREFIX}/lib" \
    pip install --upgrade SpeechRecognition psutil requests pyaudio audioop-lts standard-aifc standard-chunk

# Ensure scripts have executable permissions
chmod +x jarvis.py setup.sh run.sh 2>/dev/null || true

# Start Ollama service and ensure model is ready
echo "[+] Initializing Ollama local AI server..."
brew services start ollama 2>/dev/null || true

for i in $(seq 1 15); do
    curl -s http://127.0.0.1:11434 > /dev/null && break
    sleep 1
done

echo "[+] Pulling Llama 3.2 model for offline intelligence..."
ollama pull llama3.2

echo "================================================="
echo " [✓] Setup complete!"
echo " Start JARVIS with:"
echo "     ./run.sh"
echo " or for FRIDAY persona:"
echo "     ./run.sh friday"
echo ""
echo " Note: On first run, grant Terminal microphone access"
echo " in System Settings > Privacy & Security > Microphone."
echo "================================================="
