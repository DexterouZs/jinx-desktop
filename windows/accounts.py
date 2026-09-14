"""Private connection setup, separate from any public/profile archive."""
from pathlib import Path
import json
import os
import urllib.request,urllib.error
from PySide6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QLineEdit,QPushButton,QLabel,QComboBox,QMessageBox

def show(parent,data):
 dialog=QDialog(parent);dialog.setWindowTitle('Private account connections');dialog.resize(570,420)
 layout=QVBoxLayout(dialog);info=QLabel('Keys stay in your Windows account’s Credential Manager.\nThey are never included in a Jinx export. Blank fields keep existing keys.');info.setWordWrap(True);layout.addWidget(info)
 form=QFormLayout();layout.addLayout(form)
 online=QLineEdit();online.setEchoMode(QLineEdit.EchoMode.Password);form.addRow('Online model API key',online)
 morgen=QLineEdit();morgen.setEchoMode(QLineEdit.EchoMode.Password);form.addRow('Morgen API key',morgen)
 calendar=QComboBox();form.addRow('Morgen calendar',calendar)
 connect=QPushButton('Check Morgen and list calendars');layout.addWidget(connect)
 def store(name,value):
  import win32cred
  win32cred.CredWrite({'Type':win32cred.CRED_TYPE_GENERIC,'TargetName':'Jinx/'+name,'CredentialBlob':value.strip().encode('utf-8'),'Persist':win32cred.CRED_PERSIST_LOCAL_MACHINE,'UserName':'Jinx'},0)
 def key():
  if morgen.text().strip():return morgen.text().strip()
  import win32cred
  raw=win32cred.CredRead('Jinx/morgen-api.key',win32cred.CRED_TYPE_GENERIC)['CredentialBlob']
  return raw.decode('utf-8') if isinstance(raw,bytes) else raw
 def load():
  try:
   secret=key()
   # Fixed provider endpoint. Never forward a credential through a redirect.
   class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None
   req=urllib.request.Request('https://api.morgen.so/v3/calendars/list',headers={'Authorization':'ApiKey '+secret,'Accept':'application/json'})
   with urllib.request.build_opener(NoRedirect()).open(req,timeout=15) as r:payload=json.load(r)['data']
   rows=payload.get('calendars',[]) if isinstance(payload,dict) else payload
   calendar.clear()
   for row in rows:
    if all(isinstance(row.get(k),str) and row[k] for k in ['id','accountId','name']):calendar.addItem(row['name'],{k:row[k] for k in ['id','accountId','name']})
   if not calendar.count():raise ValueError('No calendars were returned')
  except Exception:QMessageBox.warning(dialog,'Connection not verified','Morgen did not return a usable calendar list. Check your API key, plan and internet connection.')
 connect.clicked.connect(load)
 save=QPushButton('Save private connections');layout.addWidget(save)
 def save_values():
  try:
   if online.text().strip():store('openai.key',online.text())
   if morgen.text().strip():store('morgen-api.key',morgen.text())
   selected=calendar.currentData()
   if selected:
    for name,body in [('morgen-calendar.json',selected),('calendar.json',{'preferred_app':'morgen'})]:
     path=data/name
     if path.exists():
      backup=path.with_suffix('.before-connection.json')
      if not backup.exists():backup.write_bytes(path.read_bytes())
     tmp=path.with_suffix('.new');tmp.write_text(json.dumps(body),encoding='utf-8');os.replace(tmp,path)
   online.clear();morgen.clear();dialog.accept()
  except Exception:QMessageBox.warning(dialog,'Connection not saved','Windows could not save the connection. No credential value was written to a log.')
 save.clicked.connect(save_values);dialog.exec()
