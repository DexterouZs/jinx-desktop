# Jinx for Windows — 0.2 preview

**Windows 11 x64.** This is the first native Windows edition. It shares Jinx's character, local-model approach and TalkingHead avatar renderer, with a smaller Windows-specific feature set. It is not the full KDE/Linux backend running on Windows.

## Install

1. Download **Jinx-0.2.0-preview-windows-x64-setup.exe** from [Releases](https://github.com/DexterouZs/jinx-desktop/releases).
2. Run the installer, then open **Jinx** from Start. Installation is per user; administrator privileges are not requested. No Python installation is needed.
3. In **Settings → Get Ollama**, install the official Windows Ollama application and open it. Then choose **Download everyday model** in Jinx. Allow approximately 3–4 GB for Qwen 3.5 4B; other models can be much larger.
4. Click **Refresh**, choose an installed local model, and send a message. **Think longer** is optional; leave it off for everyday conversation.
5. Press **Talk** or click the avatar. The first use asks before downloading multilingual Whisper base (approximately 150 MB). Speak, then pause. Press **Stop** to cancel. Microphone input is not continuously monitored; this preview requires another click for the next spoken turn.

The installer and portable ZIP are unsigned preview builds, so Windows may show an unknown-publisher warning. Verify downloads against the release SHA-256 file. Do not disable Defender or other system protections.

## What works in this preview

- Native dark desktop window with local streaming chat and installed-model selection.
- English/German speech recognition on CPU, English replies through installed Windows SAPI voices. British Hazel is preferred if available. Voice quality depends on the voices installed on Windows.
- A TalkingHead-compatible GLB avatar, chosen in Settings, with idle movement and simple speech motion. Mouth motion is approximate rather than phoneme-aligned. The optional free starter avatar is separately downloaded and checksum-verified, under CC BY-NC 4.0.
- Explicit SSD memory: “Remember that I prefer short answers”; edit/delete notes in Settings. New conversation clears the in-memory conversation and preserves saved notes. Conversation transcripts and microphone recordings are not written to disk.
- “Open Spotify”, “Open Steam”, “Open Notepad”, “Open Calculator”, “Open File Explorer”, “Open Settings”, “Open nexus mods website”, or “Open example.com”. App launches report that Windows accepted the request, not that playback was verified.
- “Search YouTube for ambient music” and “Search the web for …” open your browser. They do not scrape or read the search results.
- Drafting, rewriting and answering questions with the selected local model. Model-generated text never becomes an executable command.

**Not yet ported:** Linux continuous conversation/wake word, transparent always-on-top desktop placement, Breeze/F5 cloned voices, Linux/Hermes system tools, screen reading, Spotify named-track playback, Morgen calendars, email delivery, ZapZap, NPU execution and KDE/TDP integration. No Windows system administration is implied by this preview. The Linux edition retains its existing features.

## Privacy and resources

Jinx starts only when launched. It does not install a background service or open an HTTP listening port. Chat connects directly to loopback Ollama; no cloud model or API key is configured. Model/voice/avatar downloads and browser actions use the internet. Whisper audio remains in memory. Ollama's own autostart preference is managed by Ollama, separately from Jinx.

Application: `%LOCALAPPDATA%\Programs\Jinx`. Private notes, settings, selected starter avatar and recognition model: `%LOCALAPPDATA%\Jinx\data`. Ollama keeps its own models. Uninstalling Jinx removes the app and shortcuts, preserving your private data and Ollama. Use Settings → Open private data folder to manage those files deliberately.

Close Jinx before updating. The portable ZIP contains the same application and uses the same private data directory. AI model weights, your personal avatar, memories and cloned voices are not bundled.

## Build and validation

The **Windows installer** GitHub Actions workflow builds on Windows with Python 3.12, PySide6 and PyInstaller. It checks the packaged Qt WebEngine UI, imports the speech runtimes, enumerates Windows voices, installs the actual EXE, launches the installed app, and verifies that uninstall preserves private data. Build dependency versions and a smoke-test report accompany the release.

These automated checks do not prove microphone quality, real-world latency, GPU support on every PC or complete visual behaviour on a physical Windows desktop. Ollama chooses supported GPU acceleration; NPU/GPU work cannot simply be combined.

To build yourself on Windows:

```powershell
python -m pip install -r windows/requirements.txt
npm ci --ignore-scripts --prefix app/avatar3d
python windows/build.py
& "${env:ProgramFiles(x86)}\NSIS\makensis.exe" windows/installer.nsi
```

Dependencies: [PyInstaller](https://pyinstaller.org/en/stable/), [Qt for Python](https://doc.qt.io/qtforpython-6/), [Ollama for Windows](https://ollama.com/download/windows), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [NSIS](https://nsis.sourceforge.io/Docs/).
