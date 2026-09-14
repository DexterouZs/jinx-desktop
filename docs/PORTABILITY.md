# Shared assistant, native platform controls

Jinx shares conversation turn detection, task routing, model selection, memory, personality, speech text filtering, speech timing, browser research, document processing, calendar actions and message confirmation across editions. The Windows host uses the existing avatar renderer and full workspace rather than a separate reduced chat implementation.

| Area | Linux | Windows |
|---|---|---|
| Original voice | Breeze TTS2 Q8 / Vulkan | Same engine, model, reference and generation settings; Vulkan or CPU |
| Speech recognition | Local Whisper Base | Local Faster Whisper Base |
| Wake word | Vosk small English model | Same verified Vosk model |
| Desktop avatar | KDE layer-shell host | Transparent native Qt host |
| Applications/games | Installed desktop files and Steam catalogues | Windows Start menu and Steam catalogues |
| Spotify controls | MPRIS | Windows media sessions |
| System information/logs | Linux tooling and journal | Native Windows diagnostics and Event Log |
| App installation | Reviewed Linux packages | Exact WinGet packages, reviewed version, verification |
| Account keys | Private local files | Windows Credential Manager for new keys |
| Reminders | Lightweight systemd user timer | Lightweight per-user Windows task |

Both editions preserve normal OS authentication, confirmation before external messages/calendar changes, bounded tool work and cancellation. Never claim that a launched process proves playback, that a saved power limit measures battery draw, or that a missing sensor proves good health. Hardware-specific driver and device tuning is not portable.

Private NAS ZIPs include only explicitly selected voice/visual assets in addition to application installers. No credential, browser-session or memory migration is performed automatically.
