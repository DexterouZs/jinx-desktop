"""Advisory byte lock equivalent for the shared per-user job ledgers."""
import os
if os.name!='nt':
 import fcntl
else:
 import msvcrt
 class fcntl:
  LOCK_EX=1;LOCK_NB=2;LOCK_UN=4
  @staticmethod
  def flock(file, flags):
   fd=file if isinstance(file,int) else file.fileno()
   if os.fstat(fd).st_size==0:os.write(fd,b' ')
   os.lseek(fd,0,os.SEEK_SET)
   mode=msvcrt.LK_UNLCK if flags&4 else msvcrt.LK_NBLCK if flags&2 else msvcrt.LK_LOCK
   return msvcrt.locking(fd,mode,1)
