# Third-party code and assets

- **TalkingHead**, Mika Suominen: MIT. Vendored modules retain their license in `app/avatar3d/vendor/TalkingHead-LICENSE`. https://github.com/met4citizen/TalkingHead
- **Three.js**: MIT; installed from the locked npm manifest. https://github.com/mrdoob/three.js
- **Hermes Agent**, Nous Research: separate pinned upstream dependency; its own license applies. https://github.com/NousResearch/hermes-agent
- **Silero VAD**: MIT. `speech_detector.py` adapts its ONNX wrapper; model downloaded separately. https://github.com/snakers4/silero-vad
- **Piper Alba**: downloaded separately with its upstream voice/model-card terms. https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_GB/alba/medium
- **Whisper**: separately downloaded model and system runtime. https://github.com/ggml-org/whisper.cpp
- **Qwen models**: separate upstream weights; consult their model cards. https://huggingface.co/ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF
- **Qt / LayerShellQt / Ollama**: system-installed dependencies under their own licenses.

The optional starter character comes from TalkingHead's `avatars/brunette.glb`, created with Ready Player Me: **CC BY-NC 4.0**, https://creativecommons.org/licenses/by-nc/4.0/. It is downloaded by the installer, not included as an unrestricted asset. Preserve attribution and non-commercial restrictions.

The owner's custom Jinx character and recorded/cloned voices have separate provenance and are not included in GitHub releases. A private NAS ZIP can contain those personal restoration assets; that does not grant public redistribution rights. Large AI weights and trained voice caches are excluded from both source control and ordinary app updates.

The circular Jinx launcher portrait and promotional avatar screenshots are published at the project owner's request. They depict Riot Games' Jinx as fan artwork and are not relicensed under the MIT code licence; no character ownership or endorsement is claimed. The full custom 3D model and voice recordings are not publicly redistributed. The banner layout and application UI are original project work. No Whispers from the Star character, voice or proprietary pipeline is included.

## Windows bundle

PySide6/Qt is dynamically bundled under its applicable LGPL/commercial terms; LGPLv3 text and package notices are included in `third-party-licenses/`. Users may replace compatible Qt libraries in the portable application's `_internal` directory for debugging/modification under those terms. Upstream source: https://code.qt.io/ and https://code.qt.io/pyside/pyside-setup.git/ . No additional restriction is imposed on reverse engineering needed to debug those modifications.

The Windows bundle also includes faster-whisper (MIT), CTranslate2 (MIT), sounddevice/PortAudio, PyWin32, NumPy, PyAV/FFmpeg and their dependencies under their own licences. Build-time package licence files and exact versions accompany the binary. Breeze-TTS-2.cpp (Apache-2.0) and its ggml dependencies are compiled from pinned upstream sources; their notices accompany the voice library. Vosk uses its separately downloaded small English model (Apache-2.0). Whisper weights, Ollama and avatar assets download separately. The private NAS profile includes the matching Breeze Q8 weights for offline voice setup; public releases contain no private recording or original avatar model.
