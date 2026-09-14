"""David-authorized bash terminal. Raw-command denylist, not a sandbox."""
import codecs
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import time

import system_tools

# Raw text is intentional: even `echo sudo` is denied. No shell parsing.
DENYLIST = [
    ('privilege', r'\b(sudo|su|doas|pkexec)\b'),
    ('destructive', r'rm\s+(-\S*[rR]\S*\s+)+(/|~|\$HOME|/home\b|\.)(\s|$|/\*)'),
    ('destructive', r'\b(mkfs|wipefs|shred)\b'),
    ('destructive', r'\bdd\b.*\bof=/dev/'),
    ('destructive', r'>\s*/dev/(sd|nvme|mmc)'),
    ('destructive', r':\(\)\s*\{'),
    ('destructive', r'chmod\s+-R\s+\d+\s+/'),
    ('destructive', r'chown\s+-R\s+\S+\s+/(\s|$)'),
    ('power/lifecycle', r'\b(shutdown|reboot|poweroff|halt)\b'),
    ('power/lifecycle', r'systemctl\s+(poweroff|reboot|halt|suspend|hibernate|kexec)'),
    ('power/lifecycle', r'\b(ryzenadj|asusctl\s+profile|powerprofilesctl\s+set)\b'),
    ('power/lifecycle', r'(?:>|\btee\s+(?:-\S+\s+)?)\s*/sys/(class|devices)/\S*(power|fan|pwm|hwmon)\S*\s*$'),
    ('remote-code', r'(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba)?sh\b'),
    ('secrets', r'access\.key|morgen-api\.key|home-assistant\.token|\.ssh/id_|\.gnupg|/etc/shadow|kwallet|\bsecrets?\.json\b|\.config/jinx/.*\.(key|token)'),
]
DENIALS = {
    'privilege': 'Denied: privilege escalation is not available to Jinx.',
    'destructive': 'Denied: destructive disk/OS commands are not available to Jinx.',
    'power/lifecycle': 'Denied: power/lifecycle and fan changes are not available to Jinx.',
    'remote-code': 'Denied: remote-code downloads piped into a shell are not available to Jinx.',
    'secrets': 'Denied: secrets and credential files are not available to Jinx.',
}
ANSI = re.compile(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]|\x1b[@-_]')
LIMIT = 12000
MARKER = '\n[... truncated ...]\n'


def redact(text):
    text = ANSI.sub('', str(text))
    text = re.sub(r'(?i)(token|key|secret|password|bearer)\S*[=:]\s*\S+', '[redacted]', text)
    return re.sub(r'[A-Za-z0-9+/=_-]{32,}', '[redacted]', text)


class _Capture:
    """Drain both pipes continuously while retaining only bounded head/tail text."""
    def __init__(self):
        self.decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        self.head = ''
        self.tail = ''
        self.length = 0

    def add(self, chunk, final=False):
        text = self.decoder.decode(chunk, final=final)
        self.length += len(text)
        missing = LIMIT - len(self.head)
        self.head += text[:missing]
        self.tail = (self.tail + text[missing:])[-LIMIT:]

    def output(self):
        text = redact(self.head + self.tail)
        truncated = self.length > LIMIT or len(text) > LIMIT
        if len(text) > LIMIT:
            head = (LIMIT - len(MARKER)) // 2
            tail = LIMIT - len(MARKER) - head
            text = text[:head] + MARKER + text[-tail:]
        return text, truncated


def _signal_group(proc, sig):
    try:
        os.killpg(proc.pid, sig)
    except ProcessLookupError:
        pass


def run(command: str, timeout: int = 30, cwd: str | None = None) -> dict:
    started = time.monotonic()
    cwd = str(Path.home()) if cwd is None else str(cwd)
    result = dict(ok=False, exit_code=None, stdout='', stderr='', seconds=0,
                  truncated=False, denied=None)
    proc = None
    try:
        for name, pattern in DENYLIST:
            if re.search(pattern, command, re.I):
                result['denied'] = DENIALS[name]
                break
        if result['denied'] is None:
            timeout = max(1, min(120, int(timeout)))
            proc = subprocess.Popen(['/bin/bash', '-lc', command], cwd=cwd,
                                    env=None, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    start_new_session=True)
            captures = {'stdout': _Capture(), 'stderr': _Capture()}
            deadline = started + timeout
            timed_out = False
            with selectors.DefaultSelector() as selector:
                for name, pipe in [('stdout', proc.stdout), ('stderr', proc.stderr)]:
                    os.set_blocking(pipe.fileno(), False)
                    selector.register(pipe, selectors.EVENT_READ, captures[name])
                while selector.get_map() or proc.poll() is None:
                    now = time.monotonic()
                    if not timed_out and now >= deadline:
                        timed_out = True
                        _signal_group(proc, signal.SIGTERM)
                        deadline = now + 2
                    elif timed_out and now >= deadline:
                        # Kill descendants even when bash already exited on SIGTERM.
                        _signal_group(proc, signal.SIGKILL)
                        break
                    for key, _ in selector.select(min(.05, max(0, deadline-now))):
                        chunk = os.read(key.fileobj.fileno(), 65536)
                        if chunk:
                            key.data.add(chunk)
                        else:
                            selector.unregister(key.fileobj)
                # Drain remaining buffered bytes after killing, without waiting on
                # a detached descendant that kept a pipe open.
                for key in list(selector.get_map().values()):
                    for _ in range(8):
                        try:
                            chunk = os.read(key.fileobj.fileno(), 65536)
                        except BlockingIOError:
                            break
                        if not chunk:
                            break
                        key.data.add(chunk)
            proc.wait()
            result['exit_code'] = proc.returncode
            result['ok'] = proc.returncode == 0 and not timed_out
            for name, capture in captures.items():
                capture.add(b'', final=True)
                result[name], clipped = capture.output()
                result['truncated'] |= clipped
            if timed_out:
                result['stderr'] = (result['stderr'] + '\nTimed out after '+str(timeout)+' seconds.')[:LIMIT]
    except (OSError, ValueError, TypeError) as error:
        result['stderr'] = redact(str(error))[:LIMIT]
    finally:
        if proc is not None:
            if proc.poll() is None:
                _signal_group(proc, signal.SIGKILL)
                proc.wait()
            proc.stdout.close()
            proc.stderr.close()
        result['seconds'] = round(time.monotonic() - started, 3)
        system_tools.audit('shell', {
            'command': redact(command)[:300], 'cwd': redact(cwd),
            'exit_code': result['exit_code'], 'seconds': result['seconds'],
            'denied': result['denied'], 'stdout': redact(result['stdout'])[:200],
            'stderr': redact(result['stderr'])[:200],
        })
    return result
