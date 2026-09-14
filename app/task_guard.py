"""Per-turn execution budget shared by local and online registered tools.

This prevents repeated dispatch; it is not a shell sandbox or a transaction
rollback. In-flight tools finish under their own existing timeouts.
"""
import hashlib
import json
import shlex
import threading
import time

READ_TOOLS = frozenset(('jinx_diagnostics','jinx_system','jinx_logs','jinx_knowledge',
 'jinx_document','jinx_calculate','jinx_homelab','jinx_skill','jinx_home',
 'jinx_calendar','jinx_web_search','jinx_web_read','jinx_memory','jinx_recall'))
READ_ACTIONS = {'jinx_apps': {'list'}, 'jinx_music': {'status'},
 'jinx_desktop': {'status'}, 'jinx_software': {'search','info','status'}}


def read_only(name, args):
    if name == 'jinx_shell':
        # Permit before/after checks with a small set of plain read commands.
        # Unknown shell syntax remains an action, never presumed harmless.
        try:
            lex = shlex.shlex(str(args.get('command','')), posix=True, punctuation_chars=True)
            lex.whitespace_split = True
            parts = list(lex)
        except ValueError:
            return False
        return bool(parts and parts[0] in ('free','uptime','uname','df','ps','ls',
                    'lsblk','lspci','lsusb','sensors','whoami','id','pwd') and
                    not any(any(c in part for c in ';|&><`$()\n') for part in parts))
    return name in READ_TOOLS or args.get('action') in READ_ACTIONS.get(name, set())


def fingerprint(name, args):
    fields = dict(args)
    # Timeout changes do not make a repeat shell command a new action.
    if name == 'jinx_shell':
        fields.pop('timeout', None)
        if isinstance(fields.get('command'), str):
            fields['command'] = fields['command'].strip()
    raw = json.dumps([name, fields], sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode()).hexdigest()


def failed(result):
    if not isinstance(result, dict):
        return False
    return bool(result.get('error') or result.get('denied') or
                result.get('ok') is False or result.get('exit_code') not in (None, 0) or
                result.get('status') in ('failed','error','uncertain','unconfirmed'))


class TaskGuard:
    def __init__(self, max_calls=12, seconds=180, clock=time.monotonic):
        self.clock = clock
        self.deadline = clock() + seconds
        self.max_calls = max_calls
        self.calls = 0
        self.seen = {}
        self.failures = {}
        self.writes = {}
        self.reason = ''
        self.last_tool = ''
        self.last_failed = False
        self.lock = threading.RLock()

    def stop(self, reason):
        with self.lock:
            if not self.reason:
                self.reason = reason
            return self.blocked()

    def expired(self):
        with self.lock:
            if not self.reason and self.clock() >= self.deadline:
                self.reason = 'the task reached its time limit'
            return bool(self.reason)

    def blocked(self):
        return {'error': 'Task stopped: ' + self.reason, 'task_stopped': True,
                'instruction': 'Do not retry or switch tools to repeat this action. Report the limitation and await a new user request.'}

    def before(self, name, args):
        with self.lock:
            if self.expired():
                return self.blocked()
            if self.calls >= self.max_calls:
                return self.stop('the task reached its tool-call limit')
            key = fingerprint(name, args)
            reading = read_only(name, args)
            if self.seen.get(key, 0) >= (2 if reading else 1):
                return self.stop('the assistant tried to repeat the same ' + ('check' if reading else 'action'))
            if not reading and self.writes.get(name, 0) >= 4:
                return self.stop('the assistant kept using the same action tool without finishing')
            self.seen[key] = self.seen.get(key, 0) + 1
            self.calls += 1
            if not reading:
                self.writes[name] = self.writes.get(name, 0) + 1
            self.last_tool = name
            return None

    def after(self, name, result):
        with self.lock:
            self.last_failed = failed(result)
            if isinstance(result, dict) and result.get('denied'):
                self.stop('the requested operation was denied')
            if self.last_failed:
                self.failures[name] = self.failures.get(name, 0) + 1
                if self.failures[name] >= 3:
                    self.stop('the same tool failed three times')
            self.expired()

    def snapshot(self):
        with self.lock:
            return {'calls': self.calls, 'limit': self.max_calls, 'stopped': bool(self.reason),
                    'reason': self.reason, 'last_tool': self.last_tool, 'last_failed': self.last_failed}

    def reply(self):
        with self.lock:
            line = 'I stopped because ' + self.reason + '.'
            if self.last_failed:
                line += ' The last tool reported a failure.'
            if self.writes:
                line += ' Earlier steps may already have taken effect; I have not repeated them.'
            return line + ' The task is incomplete. Tell me whether you want to continue from the current state.'
