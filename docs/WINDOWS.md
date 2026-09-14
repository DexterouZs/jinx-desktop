# Jinx for Windows

The Windows edition now uses the shared Jinx assistant backend, with a native transparent desktop avatar and the full reading, writing, memory and settings workspace.

## Your original Jinx

Use the separate **Jinx-Windows.zip** on your NAS. Extract it, run the included setup EXE, then open Jinx setup and import the **personal-profile** folder. This supplies your original 3D character, reference recording and matching Breeze TTS2 Q8 model. Prepare the remaining local AI/speech models, then choose **Start Jinx**.

The public download contains no private profile, accounts, passwords, API keys, personal memory or chat history. Other users can choose a free starter avatar/Alba voice or import their own compatible profile. Account connections must be configured on each computer; new Windows provider keys are saved in Windows Credential Manager.

## Using Jinx

Click her body once to start a fresh conversation. She detects the end of your speech, answers and listens again. Click again to stop. Ctrl+Alt+J starts/stops talking, and the tray menu opens settings or puts Jinx to sleep. Sleeping Jinx releases her backend, avatar and owned model processes. Applications she launches and an authorised Windows installation have their own lifetime.

The three-dot avatar menu provides movement, size, voice, model and screen-reading controls. Blue corners indicate an explicitly requested primary-screen snapshot. Read or write documents, use copied text, research public websites, save memories, open installed apps and Steam titles, and control signed-in Spotify playback. WhatsApp uses a dedicated, visible Edge window and keeps exact-recipient/read-back confirmation before sending. Windows diagnostics use native system information and Event Log; installations use reviewed exact WinGet IDs and version verification.

Connect Morgen in setup for calendar actions. A lightweight user task delivers due reminders without loading AI when Jinx is closed; Windows notification/Focus Assist settings still control whether notifications appear. Uninstall removes the task and app files, while retaining your private data and models.

## Requirements and limits

Use 64-bit Windows with current graphics/audio drivers, Ollama, and enough RAM/storage for the selected models. Setup allows roughly 20 GB for both language models and speech assets. The everyday model is Qwen 3.5 4B; advanced tasks use the same configured Qwen 27B alias as Linux. Breeze uses Vulkan when available, with a slower CPU fallback. It does not combine NPU/GPU throughput.

The Windows adapters are new. Build/import, installer and synthetic speech tests are distinct from testing your physical GPU, microphone and signed-in apps. Performance depends on the PC. Windows-specific replacements cover common tasks; Linux kernel, ASUS fan/undervolt controls, KDE and SteamOS session switching do not transfer to another Windows computer. Arbitrary PowerShell administration is not exposed; bounded diagnostics and reviewed app installation are available.

Only Breeze and Alba are enabled in the Windows voice picker. The separate Linux F5 and Kokoro environments are not bundled. English/German recognition remains local; replies use the selected English voice. Your original Breeze timbre requires the private recording, which is intentionally absent from GitHub.
