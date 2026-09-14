"""Least-privilege user task for reminders; never starts AI or requests a password."""
import datetime,getpass,os
from pathlib import Path

def register(bundle,enabled=True):
 import win32com.client
 scheduler=win32com.client.Dispatch('Schedule.Service');scheduler.Connect();folder=scheduler.GetFolder('\\')
 name='Jinx personal reminders'
 if not enabled:
  try:folder.DeleteTask(name,0)
  except Exception:pass
  return
 task=scheduler.NewTask(0);task.RegistrationInfo.Description='Deliver due Jinx reminders without loading AI or the avatar.'
 user=os.environ.get('USERDOMAIN','')+'\\'+getpass.getuser()
 task.Principal.UserId=user;task.Principal.LogonType=3;task.Principal.RunLevel=0
 task.Settings.Enabled=True;task.Settings.StartWhenAvailable=True;task.Settings.DisallowStartIfOnBatteries=False;task.Settings.StopIfGoingOnBatteries=False;task.Settings.WakeToRun=False;task.Settings.MultipleInstances=2;task.Settings.ExecutionTimeLimit='PT2M'
 trigger=task.Triggers.Create(2);trigger.StartBoundary=datetime.datetime.now().isoformat(timespec='seconds');trigger.DaysInterval=1;trigger.Repetition.Interval='PT1M';trigger.Repetition.Duration='P1D'
 action=task.Actions.Create(0);action.Path=str(Path(bundle)/'runtime/pythonw.exe');action.Arguments='"'+str(Path(bundle)/'windows/reminder_check.py')+'"';action.WorkingDirectory=str(bundle)
 folder.RegisterTaskDefinition(name,task,6,user,'',3)
 if not folder.GetTask(name).Enabled:raise RuntimeError('Windows did not enable reminder delivery')
