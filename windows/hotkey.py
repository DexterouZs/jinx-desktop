"""Native Ctrl+Alt+J shortcut and Windows suspend notification."""
import ctypes,os
from ctypes import wintypes
from PySide6.QtCore import QAbstractNativeEventFilter,QTimer

class NativeEvents(QAbstractNativeEventFilter):
 def __init__(self,owner):
  super().__init__();self.owner=owner;self.registered=False
  if os.name=='nt':self.registered=bool(ctypes.windll.user32.RegisterHotKey(None,0x4A58,0x0001|0x0002|0x4000,ord('J')))
 def nativeEventFilter(self,event_type,message):
  if os.name=='nt':
   msg=wintypes.MSG.from_address(int(message))
   if msg.message==0x0312 and msg.wParam==0x4A58:QTimer.singleShot(0,self.owner.talk);return True,0
   if msg.message==0x0218 and msg.wParam==4:QTimer.singleShot(0,self.owner.sleep)
  return False,0
 def close(self):
  if self.registered:ctypes.windll.user32.UnregisterHotKey(None,0x4A58);self.registered=False
