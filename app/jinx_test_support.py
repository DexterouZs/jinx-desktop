"""Process-lifetime fixtures; import before jinx in every integration test module.

Keep the memory instance isolated for the whole interpreter, including daemon
episode writers that outlive a test's STATE/data patches. Never restore a real
memory instance between tests. TemporaryDirectory cleans up at interpreter exit.
"""
import os
from pathlib import Path
import tempfile

state_directory = tempfile.TemporaryDirectory(prefix='jinx-test-state-')
STATE = Path(state_directory.name)
# Override even a caller-provided path: tests must never use deployed state.
os.environ['JINX_STATE_DIR'] = str(STATE)

# Screen attention is also created during jinx import.
os.environ['XDG_RUNTIME_DIR'] = str(STATE / 'runtime')
from unittest.mock import patch
import screen_view
screen_view.RUNTIME = STATE / 'runtime' / 'jinx-attention'

# LongMemory captures this embedder at construction; restore the module function
# afterward so standalone backend tests still exercise the real implementation.
with patch('long_memory.local_embed', lambda texts: [[1.0, 0.0] for _ in texts]):
    import jinx

assert jinx.memory.path == STATE / 'memory.sqlite3'
