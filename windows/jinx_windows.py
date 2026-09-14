"""Jinx Windows preview: a native, on-demand app with no background HTTP listener."""
from __future__ import annotations
import ctypes
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import traceback
import urllib.error

from PySide6.QtCore import QObject, QThread, QTimer, QUrl, Signal, Slot, Qt
from PySide6.QtGui import QColor, QDesktopServices, QIcon
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QComboBox, QCheckBox, QDialog, QFormLayout,
    QDialogButtonBox, QFileDialog, QMessageBox, QSplitter)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage
from PySide6.QtWebChannel import QWebChannel
from core import (VERSION, DEFAULT_MODEL, Ollama, atomic_json, data_dir, direct_action,
                  load_settings, speech_text, download_verified)

ROOT = Path(__file__).resolve().parent
CREATE_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
STYLE = '''
QWidget {background:#151821;color:#e6e9ee;font-family:"Segoe UI";font-size:14px;}
QMainWindow {background:#151821;} QLabel#title {font-size:30px;font-weight:600;}
QLabel#hint {color:#a4aebe;} QTextEdit,QLineEdit,QComboBox {background:#1e2330;border:1px solid #353e50;border-radius:10px;padding:10px;selection-background-color:#42616c;}
QPushButton {background:#293441;border:1px solid #3c4a58;border-radius:9px;padding:9px 14px;}
QPushButton:hover {background:#354c58;} QPushButton:disabled {color:#707886;}
QPushButton#primary {background:#305a63;border-color:#4c8490;} QSplitter::handle {background:#252b38;}
QCheckBox {spacing:8px;} QDialog {background:#151821;}
'''

class Worker(QThread):
    event = Signal(str, str)
    failed = Signal(str)
    def __init__(self, function):
        super().__init__()
        self.function = function
        self.cancel = threading.Event()
    def run(self):
        try:
            self.function(self)
        except Exception as error:
            message = str(error)
            if isinstance(error, (urllib.error.URLError, ConnectionError)):
                message = 'Could not reach local Ollama. Install/open Ollama, then refresh models. ' + message
            self.failed.emit(message[:700])

class LocalPage(QWebEnginePage):
    def acceptNavigationRequest(self, url, nav_type, is_main):
        # No external page can inherit the native bridge.
        return url.scheme() in ('file', 'qrc', 'about')

class Bridge(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
    @Slot()
    def ready(self):
        self.window.load_avatar()
    @Slot()
    def talk(self):
        self.window.record()
    @Slot(str)
    def avatarError(self, message):
        self.window.hint.setText('Avatar failed to load; chat remains available.')

class Window(QMainWindow):
    def __init__(self, state_root=None, smoke=False):
        super().__init__()
        self.store = Path(state_root) if state_root else data_dir()
        self.store.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.store/'settings.json'
        self.config_error = ''
        try:
            self.settings = load_settings(self.settings_path)
        except (ValueError, OSError) as error:
            # Preserve malformed settings for recovery instead of silently overwriting.
            self.settings = load_settings(self.store/'missing-defaults.json')
            self.config_error = 'Settings could not be read. Original file preserved: ' + str(error)
        self.worker = None
        self.closing = False
        self.messages = []
        self.transcript = []
        self.answer = ''
        self.recognizer = None
        self.client = Ollama()
        self.smoke = smoke
        self.setWindowTitle('Jinx · Windows preview')
        self.setWindowIcon(QIcon(str(ROOT/'jinx.ico')))
        self.resize(980, 710)
        central = QWidget(); self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 18, 24, 22)
        header = QHBoxLayout(); layout.addLayout(header)
        title = QLabel('Jinx'); title.setObjectName('title'); header.addWidget(title)
        header.addStretch()
        self.settings_button = QPushButton('Settings'); self.settings_button.clicked.connect(self.configure); header.addWidget(self.settings_button)
        new = QPushButton('New conversation'); new.clicked.connect(self.new_conversation); header.addWidget(new); self.new_button = new
        self.hint = QLabel('Local AI · Private notes · Click to talk'); self.hint.setObjectName('hint'); self.hint.setWordWrap(True); layout.addWidget(self.hint)
        split = QSplitter(); layout.addWidget(split, 1)
        self.chat = QTextEdit(); self.chat.setReadOnly(True); split.addWidget(self.chat)
        self.web = QWebEngineView(); self.web.setMinimumWidth(240)
        self.web.setPage(LocalPage(self.web))
        self.web.page().setBackgroundColor(QColor(21, 24, 33))
        self.web.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        self.channel = QWebChannel(self.web.page()); self.bridge = Bridge(self)
        self.channel.registerObject('jinx', self.bridge); self.web.page().setWebChannel(self.channel)
        split.addWidget(self.web); split.setSizes([610, 290])
        self.web.setUrl(QUrl.fromLocalFile(str(ROOT/'avatar.html')))
        models = QHBoxLayout(); layout.addLayout(models)
        models.addWidget(QLabel('Model'))
        self.model = QComboBox(); self.model.setMinimumWidth(210); self.model.addItem(self.settings['model']); models.addWidget(self.model, 1)
        self.refresh = QPushButton('Refresh'); self.refresh.clicked.connect(self.refresh_models); models.addWidget(self.refresh)
        self.deep = QCheckBox('Think longer'); models.addWidget(self.deep)
        self.speak = QCheckBox('Speak'); self.speak.setChecked(self.settings['speak']); models.addWidget(self.speak)
        self.speak.toggled.connect(self.save_controls)
        row = QHBoxLayout(); layout.addLayout(row)
        self.input = QLineEdit(); self.input.setPlaceholderText('Talk, draft, or try “Open Spotify”…'); self.input.returnPressed.connect(self.send); row.addWidget(self.input, 1)
        self.send_button = QPushButton('Send'); self.send_button.setObjectName('primary'); self.send_button.clicked.connect(self.send); row.addWidget(self.send_button)
        self.mic = QPushButton('Talk'); self.mic.clicked.connect(self.record); row.addWidget(self.mic)
        self.stop_button = QPushButton('Stop'); self.stop_button.clicked.connect(self.stop); row.addWidget(self.stop_button)
        self.transcript.append(('Jinx', 'Hello. Choose a local model and we can talk. Settings includes first-time setup, voices, private notes and your avatar.'))
        self.render()
        if self.config_error:
            self.hint.setText(self.config_error)
        elif not smoke:
            QTimer.singleShot(100, self.refresh_models)

    def save_controls(self):
        if self.config_error:
            self.hint.setText(self.config_error)
            return
        self.settings['speak'] = self.speak.isChecked()
        self.settings['model'] = self.model.currentText()
        atomic_json(self.settings_path, self.settings)

    def render(self):
        text = '\n\n'.join(f'{name}\n{content}' for name, content in self.transcript)
        if self.answer:
            text += '\n\nJinx\n' + self.answer
        self.chat.setPlainText(text)
        bar = self.chat.verticalScrollBar(); bar.setValue(bar.maximum())

    def phase(self, text):
        self.hint.setText(text)
        self.web.page().runJavaScript('window.jinxAvatar?.state(' + json.dumps(text) + ')')

    def busy(self, value):
        for widget in (self.send_button, self.mic, self.refresh, self.model, self.settings_button, self.new_button, self.deep):
            widget.setEnabled(not value)
        self.stop_button.setEnabled(value)

    def work(self, function, finished=None):
        if self.worker:
            return
        worker = Worker(function); self.worker = worker; self.busy(True)
        worker.event.connect(self.event)
        worker.failed.connect(self.error)
        def finish():
            self.worker = None; self.busy(False)
            if not self.closing:
                if finished: finished()
                if not self.worker and not self.hint.text().startswith('Error:'): self.phase('Ready')
            else:
                self.close()
            worker.deleteLater()
        worker.finished.connect(finish)
        worker.start()

    def error(self, message):
        self.phase('Error: ' + message)
        self.transcript.append(('Jinx', message)); self.render()

    def event(self, kind, value):
        if kind == 'phase': self.phase(value)
        elif kind == 'token': self.answer += value; self.render()
        elif kind == 'models':
            old = self.settings['model']; values = json.loads(value)
            self.model.clear(); self.model.addItems(values or [DEFAULT_MODEL])
            index = self.model.findText(old)
            if index >= 0: self.model.setCurrentIndex(index)
            if not values: self.phase('No local models yet. Open Settings → Download everyday model.')
        elif kind == 'transcription': self.input.setText(value)
        elif kind == 'avatar':
            self.settings['avatar'] = value; self.save_controls(); self.load_avatar()
        elif kind == 'voices': self.available_voices = json.loads(value)

    def refresh_models(self):
        def task(w):
            w.event.emit('phase', 'Checking local Ollama…')
            w.event.emit('models', json.dumps(self.client.models()))
        self.work(task)

    def new_conversation(self):
        if self.worker: return
        self.messages.clear(); self.transcript.clear(); self.answer = ''; self.render(); self.phase('Ready')

    def send(self):
        if self.worker: return
        text = self.input.text().strip()
        if not text: return
        if len(text) > 12000:
            self.error('Please keep each message under 12,000 characters.'); return
        self.input.clear(); self.transcript.append(('You', text)); self.render(); self.save_controls()
        try:
            action = direct_action(text)
            if action:
                result = self.perform(action)
                self.transcript.append(('Jinx', result))
                self.messages.extend([{'role': 'user', 'content': text}, {'role': 'assistant', 'content': result}])
                self.render(); self.say(result); return
        except Exception as error:
            self.error(str(error)); return
        self.messages.append({'role': 'user', 'content': text})
        model = self.model.currentText(); notes = self.settings['notes']; think = self.deep.isChecked()
        self.answer = ''
        def task(w):
            w.event.emit('phase', 'Thinking…')
            for token in self.client.chat(model, list(self.messages), notes, think, w.cancel):
                w.event.emit('token', token)
        def done():
            if self.answer:
                answer = self.answer; self.answer = ''
                self.messages.append({'role': 'assistant', 'content': answer})
                self.transcript.append(('Jinx', answer)); self.render()
                if not self.cancelled: self.say(answer)
        self.cancelled = False
        self.work(task, done)

    def perform(self, action):
        kind, value = action
        if kind == 'remember':
            if self.config_error: raise ValueError(self.config_error)
            self.settings['notes'] = (self.settings['notes'] + '\n' + value).strip()[-12000:]
            self.save_controls(); return 'Saved to your private notes on this computer. You can edit or delete it in Settings.'
        if kind == 'unsupported':
            return 'This Windows preview cannot launch that app yet. Supported names: Spotify, Steam, Notepad, Calculator, File Explorer, Settings or a website address.'
        if kind == 'url':
            if not QDesktopServices.openUrl(QUrl(value)): raise RuntimeError('Windows did not accept the browser launch.')
            return 'Requested your browser to open ' + value
        if os.name != 'nt': raise RuntimeError('Windows app launches are only available on Windows.')
        protocols = {'spotify': 'spotify:', 'steam': 'steam://open/main', 'settings': 'ms-settings:', 'browser': 'https://www.google.com'}
        if value in protocols:
            if not QDesktopServices.openUrl(QUrl(protocols[value])): raise RuntimeError('Windows could not open the app. Check that it is installed.')
        else:
            # Fixed built-ins only, no shell and no generated arguments.
            exe = {'notepad':'notepad.exe', 'calculator':'calc.exe', 'file explorer':'explorer.exe', 'explorer':'explorer.exe'}[value]
            windows = Path(os.environ.get('SystemRoot', r'C:\Windows'))
            path = windows/exe if exe == 'explorer.exe' else windows/'System32'/exe
            subprocess.Popen([str(path)], creationflags=CREATE_NO_WINDOW)
        return 'Requested Windows to open ' + value + '. This does not verify its window or playback.'

    def say(self, text):
        if not self.speak.isChecked() or os.name != 'nt' or self.closing: return
        voice_id = self.settings['voice']
        def task(w):
            import pythoncom
            import win32com.client
            pythoncom.CoInitialize()
            try:
                speaker = win32com.client.Dispatch('SAPI.SpVoice')
                voices = list(speaker.GetVoices())
                selected = next((v for v in voices if v.Id == voice_id), None)
                if selected is None:
                    selected = next((v for v in voices if 'hazel' in v.GetDescription().lower()), None)
                if selected: speaker.Voice = selected
                w.event.emit('phase', 'Speaking')
                speaker.Rate = 0
                speaker.Speak(speech_text(text), 1 | 16)  # Async + explicitly non-XML.
                while not speaker.WaitUntilDone(80):
                    if w.cancel.is_set(): speaker.Speak('', 2); break
            finally: pythoncom.CoUninitialize()
        self.work(task)

    def stop(self):
        if self.worker:
            self.cancelled = True; self.worker.cancel.set(); self.phase('Stopping…')

    def record(self):
        if self.worker: self.stop(); return
        if not (self.store/'speech-consent').exists():
            result = QMessageBox.question(self, 'Set up local speech',
                'Download the multilingual Whisper base model (about 150 MB) on first use? Recognition runs locally. The microphone records only after Talk is pressed, until a pause or Stop. Audio is kept in memory, not saved.')
            if result != QMessageBox.StandardButton.Yes: return
            (self.store/'speech-consent').touch()
        self.cancelled = False
        def task(w):
            import numpy as np
            import sounddevice as sd
            from faster_whisper import WhisperModel
            if self.recognizer is None:
                w.event.emit('phase', 'Loading local speech model; first use downloads about 150 MB…')
                self.recognizer = WhisperModel('base', device='cpu', compute_type='int8', cpu_threads=4, download_root=str(self.store/'speech-model'))
            if w.cancel.is_set(): return
            w.event.emit('phase', 'Listening… speak now')
            chunks = []; heard = False; silence = 0; active = 0
            # Start-stop capture; conservative energy gate plus Whisper VAD.
            with sd.InputStream(samplerate=16000, channels=1, dtype='float32', blocksize=1600) as stream:
                for index in range(250):
                    if w.cancel.is_set(): return
                    audio, overflow = stream.read(1600)
                    chunks.append(audio[:, 0].copy())
                    rms = float(np.sqrt(np.mean(audio * audio)))
                    if rms > .012:
                        active += 1; heard = heard or active >= 3; silence = 0
                    else: silence += 1
                    if heard and silence >= 12: break
                    if not heard and index >= 80: break
            if not heard:
                raise RuntimeError('No clear speech detected. Check your microphone and try again.')
            w.event.emit('phase', 'Transcribing locally…')
            segments, _ = self.recognizer.transcribe(np.concatenate(chunks), beam_size=1, vad_filter=True, condition_on_previous_text=False)
            text = ' '.join(s.text.strip() for s in segments).strip()
            if text and not w.cancel.is_set(): w.event.emit('transcription', text)
        def done():
            if not self.cancelled and self.input.text().strip() and not self.hint.text().startswith('Error:'):
                self.send()
        self.work(task, done)

    def load_avatar(self):
        path = self.settings.get('avatar')
        if path and Path(path).is_file():
            self.web.page().runJavaScript('window.jinxAvatar?.load(' + json.dumps(QUrl.fromLocalFile(path).toString()) + ')')

    def configure(self):
        dialog = QDialog(self); dialog.setWindowTitle('Jinx settings'); dialog.resize(580, 580)
        layout = QVBoxLayout(dialog)
        info = QLabel('Windows preview · Local chat, voice, notes and basic launches.\nLinux calendar, screen tools, Breeze voice and system administration are not ported.'); info.setWordWrap(True); layout.addWidget(info)
        setup = QHBoxLayout(); layout.addLayout(setup)
        ollama = QPushButton('Get Ollama'); setup.addWidget(ollama)
        ollama.clicked.connect(lambda: QDesktopServices.openUrl(QUrl('https://ollama.com/download/windows')))
        pull = QPushButton('Download everyday model'); setup.addWidget(pull)
        def download_model():
            if QMessageBox.question(dialog, 'Download model', 'Download Qwen 3.5 4B through your local Ollama? Allow about 3–4 GB of disk space and an internet connection.') != QMessageBox.StandardButton.Yes: return
            dialog.accept()
            def task(w):
                for item in self.client.pull(w.cancel):
                    total = item.get('total', 0); completed = item.get('completed', 0)
                    progress = f' {100*completed/total:.0f}%' if total else ''
                    w.event.emit('phase', str(item.get('status', 'Downloading…')) + progress)
            self.work(task, lambda: self.refresh_models() if not self.closing else None)
        pull.clicked.connect(download_model)
        form = QFormLayout(); layout.addLayout(form)
        voices = QComboBox(); voices.addItem('Windows default (British Hazel preferred)', '')
        if os.name == 'nt':
            try:
                import pythoncom, win32com.client
                pythoncom.CoInitialize()
                try:
                    sapi = win32com.client.Dispatch('SAPI.SpVoice')
                    for voice in sapi.GetVoices(): voices.addItem(voice.GetDescription(), voice.Id)
                finally: pythoncom.CoUninitialize()
            except Exception: voices.addItem('Windows speech voice unavailable', '')
        selected = voices.findData(self.settings['voice']); voices.setCurrentIndex(max(0, selected))
        form.addRow('Voice', voices)
        note_hint = QLabel('Saved notes stay on this SSD. They are included with local chat. Conversation transcripts are not saved.'); note_hint.setWordWrap(True); layout.addWidget(note_hint)
        notes = QTextEdit(); notes.setPlainText(self.settings['notes']); layout.addWidget(notes)
        avatar = QHBoxLayout(); layout.addLayout(avatar)
        choose = QPushButton('Choose avatar (.glb)'); avatar.addWidget(choose)
        starter = QPushButton('Get free starter avatar'); avatar.addWidget(starter)
        def choose_avatar():
            path, _ = QFileDialog.getOpenFileName(dialog, 'Choose compatible TalkingHead avatar', '', 'GLB avatar (*.glb)')
            if path:
                self.settings['avatar'] = path; self.save_controls(); self.load_avatar()
        choose.clicked.connect(choose_avatar)
        def get_starter():
            if QMessageBox.question(dialog, 'Starter avatar licence', 'Download the Ready Player Me starter avatar from TalkingHead? CC BY-NC 4.0: personal/non-commercial use. Your own Jinx model can instead be selected locally.') != QMessageBox.StandardButton.Yes: return
            dialog.accept()
            def task(w):
                spec = json.loads((ROOT/'starter-avatar.json').read_text())
                w.event.emit('phase', 'Downloading verified starter avatar…')
                target = self.store/'avatars/starter.glb'
                download_verified(spec['url'], target, spec['sha256'])
                w.event.emit('avatar', str(target))
            self.work(task)
        starter.clicked.connect(get_starter)
        folder = QPushButton('Open private data folder'); layout.addWidget(folder)
        folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.store))))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel); layout.addWidget(buttons)
        def save():
            if len(notes.toPlainText()) > 12000:
                QMessageBox.warning(dialog, 'Notes too long', 'Keep saved notes under 12,000 characters.'); return
            self.settings['voice'] = voices.currentData(); self.settings['notes'] = notes.toPlainText(); self.save_controls(); dialog.accept()
        buttons.accepted.connect(save); buttons.rejected.connect(dialog.reject)
        dialog.exec()

    def closeEvent(self, event):
        if self.worker:
            self.closing = True; self.stop(); self.hide(); event.ignore()
        else:
            self.save_controls(); event.accept()


def main():
    smoke = '--smoke-test' in sys.argv
    app = QApplication(sys.argv); app.setApplicationName('Jinx'); app.setStyleSheet(STYLE)
    if os.name == 'nt':
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('DexterouZs.Jinx.Desktop')
    if smoke:
        import tempfile
        with tempfile.TemporaryDirectory(prefix='jinx-smoke-') as tmp:
            window = Window(tmp, smoke=True); window.show()
            result = {'ui': False}
            def check():
                if os.name == 'nt':
                    import sounddevice, faster_whisper, pythoncom, win32com.client
                    pythoncom.CoInitialize()
                    try:
                        result['sapi_voices'] = win32com.client.Dispatch('SAPI.SpVoice').GetVoices().Count
                    finally: pythoncom.CoUninitialize()
                    result['speech_imports'] = True
                def received(value):
                    result['ui'] = bool(value)
                    Path(os.environ.get('JINX_SMOKE_REPORT', 'jinx-smoke.json')).write_text(json.dumps(result))
                    window.close(); app.quit()
                window.web.page().runJavaScript("Boolean(window.jinxAvatar && document.getElementById('stage'))", received)
            QTimer.singleShot(8000, check)
            QTimer.singleShot(45000, app.quit)
            app.exec()
            return 0 if result['ui'] else 1
    window = Window(); window.show(); return app.exec()

if __name__ == '__main__':
    raise SystemExit(main())
