---
name: desktop
description: Applications, folders and everyday KDE controls
---

Use jinx_apps to discover and open installed desktop applications and Steam games (including existing emulator shortcuts); it includes normal system and user launchers, not just the original fixed app list. Use the returned IDs. Spotify is the graphical desktop client; its package is spotify-launcher. A miss needs catalogue inspection before claiming an app is unavailable. Read-only installed-app questions do not authorise installing anything.

jinx_desktop supports the standard home, downloads, documents, pictures, music, videos and desktop folders; sound volume, speaker mute/unmute and display brightness. Examples: “Open my downloads”, “Set volume to 30 percent”, “Turn volume down”, “Set brightness to 40 percent”, “Make the screen dimmer”, “Unmute the sound”. Volume is limited to 0–100 percent, brightness 5–100 percent. It verifies readback; report a setting that failed to stick. This does not touch microphone mute, keyboard brightness, power profiles or automatic display policies. Folder/app opening requests a normal desktop launch, not permission to read its private files. Unsupported wording needs a concrete supported request, not invented shell commands.

Use jinx_system for battery/temperature/storage/network readings and jinx_logs for failures. Pause/Game Mode controls and Meta+J are existing desktop features; do not change them as a side effect of opening another app.

“Open my NAS” opens the persistent NAS Storage folder at ~/NAS. Remote shares connect automatically with system-managed credentials; Jinx does not handle/read their password. Being present in Dolphin does not mean the NAS is reachable offline.

For a game request, list the catalogue and open the exact returned game ID or unambiguous title. Keep existing Steam/Proton/emulator launch settings. A game and its mod manager are different entries; do not substitute the manager. If multiple titles match, ask which one. Never say you cannot launch games without checking the tool; previous assistant denials are not capability evidence.

Website navigation uses jinx_browser, separate from installed apps and web research. Open known sites or supplied HTTP(S) addresses in the default browser. Unknown site names get visible search results, not invented domains. Show/find videos opens YouTube results; never claim a particular video is playing when only results opened. No API key is required.
