# Architecture

One application launcher starts a native Qt Quick / WebEngine window using LayerShellQt on KDE Wayland. Three.js and TalkingHead render the avatar. The authenticated loopback backend runs on port17341; Ollama uses port11435. Services run as the desktop user, and AI services start on demand.

`app/jinx.py` owns conversation state, direct task routes and guarded model tools. `routing.py` selects the fast or capable model independently from explicit reasoning requests. `task_guard.py` bounds repeated calls. Recognition uses CPU Whisper with Silero VAD; Piper is the fresh-install speech default. Optional Breeze runs in an isolated worker. Private state lives outside the installation tree.

Direct workflows handle common requests before model reasoning: browser launch, timer/calculation, notes, calendar dialogue and the bounded default news brief. The model retains tools for tasks that need them. Settings, memory and connected services are accessed through the local workspace.

Tests import `jinx_test_support` before the backend to isolate state. Do not use real messages, credentials or appointments as fixtures. Device-specific tools are optional; missing software/accounts must produce an honest error instead of a success claim.
