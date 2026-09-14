# Install and restore

Supported first release: x86-64 Arch/CachyOS, KDE Plasma 6 Wayland, systemd user services and PipeWire. GPU support depends on Ollama and your driver. The tested configuration has 32 GB unified memory and 16 GB GPU allocation; other systems are not certified.

1. Extract the release ZIP to an ordinary writable directory.
2. Run `bash "Install Jinx.sh" --check` to see missing packages.
3. Run `bash "Install Jinx.sh" --install-deps`. Pacman uses normal administrator authentication when dependencies are missing.
4. Open Jinx from the application menu. Click the wake widget, then click the avatar to talk.

The full install downloads both language models. `--models everyday` downloads only 4B: complex/tool requests that need 27B will be unavailable until it is installed. `--models none` is intended for an existing model store. Speech assets, including the small Vosk wake-word model, are separately checksum-verified. Wake-word listening starts disabled. Clicking to talk uses Whisper/Silero and works independently.

The private Linux NAS ZIP adds a `personal-profile` folder with the original avatar, reference recording and matching Breeze voice weights. The installer verifies and imports only these named assets, builds the matching voice engine and selects Breeze. It does not transfer accounts, passwords or personal memory. Keep this ZIP private; use the clean Linux release for public distribution.

The first installation needs internet. This ZIP is not a fully offline copy of model weights, package repositories or Python wheels. Installation errors stop with an explanation rather than weakening permissions.

## Locations

| Content | Location |
|---|---|
| Application and isolated environment | `~/Jinx` |
| Models | `~/.local/share/jinx/models` |
| Private settings, credentials and memory | `~/.local/state/jinx` |
| Previous app and changed integration files | `~/.local/share/jinx/installer-backups/<timestamp>` |
| Desktop launcher | `~/.local/share/applications/jinx.desktop` |

AI and avatar services are not enabled at login. A lightweight reminder timer checks due items once a minute without loading a model or avatar. Existing custom service drop-ins are preserved; review incompatible old overrides if restoring on another machine. The application menu entry starts Jinx's lightweight widget, and the sleep control stops the AI services. Existing keyboard shortcuts can call `jinx-desktop-control talk`; this installer does not rewrite your KDE shortcuts.

## Updating and recovery

An existing `~/Jinx` is protected unless you pass `--update`. The installer prepares and checks a new build first, preserves your avatar/voice assets, stops running Jinx services, and moves the previous app into the timestamped backup. Private state is never deleted or reset. Failed downloads preserve the previous files.

To undo an update, stop the three Jinx user services, move the new `~/Jinx` aside, move the backup's `previous-app` directory back to `~/Jinx`, and restore its backed-up `.config`/`.local` integration files to their corresponding home locations. Run `systemctl --user daemon-reload`. Keep both trees until the restored app works. Recovery is manual; a failed post-install dependency/model download does not automatically roll back.

To remove the app, stop `jinx-desktop`, `jinx` and `jinx-model`, disable `jinx-reminders.timer`, remove the installed Jinx user unit files and launcher, then move `~/Jinx` aside. Keep private state/models until you decide whether to retain them. Do not remove unrelated system packages.
