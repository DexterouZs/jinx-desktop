"""Small persistent style description shared by the fast and capable models."""
from pathlib import Path

def instructions():
 try:
  text=Path(__file__).with_name('PERSONALITY.md').read_text()
  return 'Character and conversational style:\n'+text.partition('\n')[2].strip()[:1800]
 except OSError:return 'Be warm, witty, candid and useful. Never invent memories or completed actions.'
