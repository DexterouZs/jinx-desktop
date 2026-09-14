"""Native transparent Windows host for Jinx's shared avatar and full workspace."""
from pathlib import Path
import ctypes,json,os,secrets,shutil,subprocess,sys,time,urllib.request
from PySide6.QtCore import QTimer,QUrl,Qt,QProcess,QProcessEnvironment,QPoint,QLockFile
from PySide6.QtGui import QColor,QIcon,QPainter,QPen,QDesktopServices
from PySide6.QtWidgets import QApplication,QWidget,QMainWindow,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QDialog,QFileDialog,QMessageBox,QTextEdit,QSystemTrayIcon,QMenu
from PySide6.QtWebEngineCore import QWebEnginePage,QWebEngineProfile,QWebEngineUrlRequestInterceptor,QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

BUNDLE=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]
ASSETS=Path(__file__).resolve().parent
DATA=Path(os.environ.get('JINX_STATE_DIR',str(Path(os.environ.get('LOCALAPPDATA',Path.home()))/'Jinx/data')))
MODELS=Path(os.environ.get('JINX_MODELS_DIR',str(DATA.parent/'models')))
RUNTIME=DATA/'runtime'
ORIGIN='http://127.0.0.1:'+os.environ.get('JINX_PORT','17341')
STYLE='QDialog,QMainWindow{background:#14171e;color:#e5e8ef} QLabel,QTextEdit{color:#e5e8ef} QPushButton{color:#e5e8ef;background:#293341;border:1px solid #465266;border-radius:10px;padding:9px} QTextEdit{background:#1b202a;border:0;padding:10px}'

def atomic(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value),encoding='utf-8');os.replace(tmp,path)

def python():return str(BUNDLE/'runtime/python.exe') if (BUNDLE/'runtime/python.exe').is_file() else sys.executable

def env():
 result=QProcessEnvironment.systemEnvironment()
 for k,v in {'JINX_STATE_DIR':str(DATA),'JINX_MODELS_DIR':str(MODELS),'XDG_RUNTIME_DIR':str(RUNTIME),'PYTHONUTF8':'1','PYTHONPATH':str(BUNDLE/'app')+os.pathsep+str(BUNDLE/'hermes'),'JINX_BREEZE_LIBRARY':str(BUNDLE/'voice/jinx-breeze.dll'),'JINX_BREEZE_ALLOW_CPU':'1'}.items():result.insert(k,v)
 return result

class Interceptor(QWebEngineUrlRequestInterceptor):
 def interceptRequest(self,info):
  u=info.requestUrl()
  if u.scheme()=='http' and u.host()=='127.0.0.1' and u.port()==int(ORIGIN.rsplit(':',1)[1]):info.setHttpHeader(b'X-Jinx-Token',TOKEN.encode())
  elif u.scheme() not in ('data','blob','about'):info.block(True)

class Page(QWebEnginePage):
 def acceptNavigationRequest(self,url,kind,main):
  if self.property('smoke') and url.scheme()=='data':return True
  return url.toString().startswith(ORIGIN+'/') or url.toString()=='about:blank'

class Corners(QWidget):
 def __init__(self):
  super().__init__(None,Qt.WindowType.FramelessWindowHint|Qt.WindowType.Tool|Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.WindowTransparentForInput)
  self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground);self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
  self.setGeometry(QApplication.primaryScreen().geometry())
 def paintEvent(self,event):
  p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setPen(QPen(QColor(75,176,255,210),5))
  w,h=self.width(),self.height()
  for x,y,sx,sy in [(8,8,1,1),(w-8,8,-1,1),(8,h-8,1,-1),(w-8,h-8,-1,-1)]:
   p.drawLine(x,y,x+45*sx,y);p.drawLine(x,y,x,y+45*sy)

class Workspace(QMainWindow):
 def __init__(self,owner):
  super().__init__();self.setWindowTitle('Jinx · Settings and workspace');self.resize(960,840)
  self.view=owner.webview(self,transparent=False);self.setCentralWidget(self.view);self.view.loadFinished.connect(lambda ok:owner.platform_options(self.view) if ok else None);self.view.setUrl(QUrl(ORIGIN+'/'))

class Setup(QDialog):
 def __init__(self,owner):
  super().__init__(owner);self.owner=owner;self.process=None;self.setWindowTitle('Set up Jinx');self.resize(650,520);self.setStyleSheet(STYLE)
  box=QVBoxLayout(self)
  label=QLabel('Use your original voice and avatar, with the full Jinx assistant.\nImport the private profile from your NAS, then prepare the local models.');label.setWordWrap(True);box.addWidget(label)
  row=QHBoxLayout();box.addLayout(row)
  folder=QPushButton('Import NAS profile folder');folder.clicked.connect(self.import_profile);row.addWidget(folder)
  archive=QPushButton('Import Windows NAS ZIP');archive.clicked.connect(lambda:self.import_profile(True));row.addWidget(archive)
  starter=QPushButton('Use a free starter avatar and voice');starter.clicked.connect(self.starter);box.addWidget(starter)
  accounts=QPushButton('Connect my accounts privately');accounts.clicked.connect(self.accounts);box.addWidget(accounts)
  self.log=QTextEdit();self.log.setReadOnly(True);box.addWidget(self.log)
  row=QHBoxLayout();box.addLayout(row)
  ollama=QPushButton('Install / open Ollama');ollama.clicked.connect(lambda:QDesktopServices.openUrl(QUrl('https://ollama.com/download/windows')));row.addWidget(ollama)
  self.download=QPushButton('Prepare models');self.download.clicked.connect(self.prepare);row.addWidget(self.download)
  ready=QPushButton('Start Jinx');ready.clicked.connect(self.start);row.addWidget(ready)
  self.log.setPlainText('Account keys and passwords are never imported from a release. Connect your own services privately after installation.\n\nModels need about 20 GB of free space and a fast connection. The 27B model is optional for everyday chat but is used for advanced tasks. Your original Breeze voice needs its model and private reference recording.')
 def accounts(self):
  import accounts
  accounts.show(self,DATA)
 def import_profile(self,archive=False):
  from personal_profile import import_folder,import_zip
  chosen=QFileDialog.getOpenFileName(self,'Choose Jinx-Windows ZIP','','ZIP (*.zip)')[0] if archive else QFileDialog.getExistingDirectory(self,'Choose the personal-profile folder')
  if not chosen:return
  self.owner.sleep()
  try:
   names=(import_zip if archive else import_folder)(chosen,DATA,MODELS)
   state=json.loads((DATA/'state.json').read_text());state.update(voice='breeze_tts2',voice_speed=1.0);atomic(DATA/'state.json',state)
   self.log.append('Imported and verified: '+', '.join(names))
  except Exception as e:QMessageBox.warning(self,'Profile not imported',str(e))
 def starter(self):
  if QMessageBox.question(self,'Starter avatar','Download the Ready Player Me starter avatar (CC BY-NC 4.0, personal/non-commercial use) and the free Alba voice? Your NAS profile supplies your original Jinx instead.')!=QMessageBox.StandardButton.Yes:return
  self.prepare(True)
 def prepare(self,starter=False):
  if self.process:return
  if not starter and QMessageBox.question(self,'Download local models','Prepare Breeze, multilingual speech recognition and the everyday/advanced local AI models? Allow around 20 GB of storage and a large download.')!=QMessageBox.StandardButton.Yes:return
  if not starter and not self.owner.start_model():return
  self.process=QProcess(self);self.process.setProcessEnvironment(env());self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
  self.process.readyReadStandardOutput.connect(lambda:self.log.append(bytes(self.process.readAllStandardOutput()).decode('utf-8',errors='replace')[-5000:]))
  def finished(code,status):
   self.download.setEnabled(True);self.log.append('Model setup completed.' if code==0 else 'Setup stopped. The last error is shown above; existing models were preserved.');self.process.deleteLater();self.process=None
  self.process.finished.connect(finished);self.download.setEnabled(False)
  self.process.start(python(),[str(BUNDLE/'windows/setup_models.py')]+(['--starter'] if starter else []))
 def start(self):
  state=json.loads((DATA/'state.json').read_text())
  if (state.get('voice')=='breeze_tts2' and not (DATA/'assets/reference-short.wav').exists()) or not (DATA/'assets/jinx-character.glb').exists():QMessageBox.information(self,'Original profile needed','Import your private Jinx profile from the NAS first.');return
  try:
   import reminder_task
   reminder_task.register(BUNDLE)
  except Exception:QMessageBox.warning(self,'Reminder delivery','Windows could not enable reminders while Jinx is closed. Reminders will still work while Jinx is open.')
  self.accept();self.owner.wake()
 def closeEvent(self,event):
  if self.process:event.ignore();self.log.append('Model setup is still running. This window stays open until it finishes.')
  else:event.accept()

class Avatar(QWidget):
 def __init__(self,smoke=False):
  super().__init__(None,Qt.WindowType.FramelessWindowHint|Qt.WindowType.Tool)
  self.setWindowTitle('Jinx');self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
  self.smoke=smoke;self.backend=None;self.model_process=None;self.jobs=[];self.work=None;self.setup=None;self.top=False;self.loaded=False;self.closing=False;self.drag_start=None;self.drag_id=None
  self.corner=Corners();self.profile=QWebEngineProfile(self);self.interceptor=Interceptor(self.profile);self.profile.setUrlRequestInterceptor(self.interceptor)
  self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
  self.web=None
  try:self.layout_state=json.loads((DATA/'avatar-layout.json').read_text())
  except (OSError,ValueError):self.layout_state={'scale':.85,'unlocked':False}
  self.skill=QPushButton(self);self.skill.setIcon(QIcon(str(ASSETS/'jinx.ico')));self.skill.setIconSize(__import__('PySide6.QtCore',fromlist=['QSize']).QSize(44,44));self.skill.setToolTip('Wake Jinx');self.skill.setStyleSheet('QPushButton{background:#b51b2636;border:2px solid #91cdd6;border-radius:27px;}');self.skill.resize(54,54);self.skill.clicked.connect(self.toggle)
  self.tray=QSystemTrayIcon(QIcon(str(ASSETS/'jinx.ico')),self);self.tray.setToolTip('Jinx')
  menu=QMenu();menu.addAction('Talk / stop',self.talk);menu.addAction('Settings',self.settings);menu.addAction('Set up voice and models',self.configure);menu.addAction('Sleep Jinx',self.sleep);menu.addSeparator();menu.addAction('Quit',self.quit)
  self.tray.setContextMenu(menu);self.tray.activated.connect(lambda reason:self.toggle() if reason==QSystemTrayIcon.ActivationReason.Trigger else None);self.tray.show()
  self.apply_layout();self.timer=QTimer(self);self.timer.timeout.connect(self.tick);self.timer.start(150)
  self.requests=set();self.next_reload=0;self.show()
  if not smoke:QTimer.singleShot(200,self.initial)
 def initial(self):
  profile=BUNDLE/'personal-profile'
  # The NAS ZIP puts private assets beside setup.exe, not in the public installer.
  if (profile/'profile.json').is_file() and not (DATA/'assets/reference-short.wav').exists():
   try:
    from personal_profile import import_folder
    import_folder(profile,DATA,MODELS)
   except Exception:pass
  state=json.loads((DATA/'state.json').read_text())
  voice_ready=state.get('voice')=='piper_alba' or (DATA/'assets/reference-short.wav').is_file()
  if voice_ready and (DATA/'assets/jinx-character.glb').is_file():self.wake()
  else:self.configure()
 def webview(self,parent,transparent=True):
  view=QWebEngineView(parent);page=Page(self.profile,view);view.setPage(page)
  page.setBackgroundColor(QColor(0,0,0,0) if transparent else QColor('#14171e'))
  view.settings().setAttribute(QWebEngineSettings.WebAttribute.ErrorPageEnabled,False)
  view.settings().setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture,False)
  page.permissionRequested.connect(lambda permission:permission.deny())
  return view
 def api(self,path,body=None):
  request=urllib.request.Request(ORIGIN+path,data=json.dumps(body).encode() if body is not None else None,headers={'X-Jinx-Token':TOKEN,'Content-Type':'application/json'})
  with urllib.request.urlopen(request,timeout=2) as response:return json.load(response)
 def start_model(self):
  try:urllib.request.urlopen('http://127.0.0.1:11435/api/tags',timeout=1).close();return True
  except OSError:pass
  executable=shutil.which('ollama') or str(Path(os.environ.get('LOCALAPPDATA',''))/'Programs/Ollama/ollama.exe')
  if not Path(executable).is_file():QMessageBox.information(self,'Ollama needed','Install Ollama, then choose Prepare models in Jinx setup.');return False
  self.model_process=QProcess(self);e=env();e.insert('OLLAMA_HOST','127.0.0.1:11435');e.insert('OLLAMA_KEEP_ALIVE','5m');e.insert('OLLAMA_FLASH_ATTENTION','1');e.insert('OLLAMA_KV_CACHE_TYPE','q4_0');e.insert('OLLAMA_NO_CLOUD','1');e.insert('OLLAMA_MODELS',str(MODELS/'ollama'));self.model_process.setProcessEnvironment(e);self.model_process.start(executable,['serve'])
  result=self.model_process.waitForStarted(3000)
  if result:self.own(self.model_process)
  return result
 def wake(self):
  if self.backend and self.backend.state()!=QProcess.ProcessState.NotRunning:return
  if not self.smoke and not self.start_model():return
  self.backend=QProcess(self);self.backend.setProcessEnvironment(env());self.backend.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
  self.backend.readyReadStandardOutput.connect(self.backend_output);self.backend.start(python(),[str(BUNDLE/'windows/backend_main.py')]);self.backend.waitForStarted(3000);self.own(self.backend);self.skill.setToolTip('Sleep Jinx · release AI resources')
  self.web=self.webview(self);self.web.setGeometry(self.rect());self.web.lower();self.web.show();self.loaded=False
  self.web.loadFinished.connect(self.page_loaded);self.web.setUrl(QUrl(ORIGIN+'/avatar/index.html'))
 def own(self,process):
  if os.name!='nt':return
  import win32job,win32api,win32con
  job=win32job.CreateJobObject(None,None);info=win32job.QueryInformationJobObject(job,win32job.JobObjectExtendedLimitInformation)
  info['BasicLimitInformation']['LimitFlags']|=win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE|win32job.JOB_OBJECT_LIMIT_BREAKAWAY_OK
  win32job.SetInformationJobObject(job,win32job.JobObjectExtendedLimitInformation,info)
  handle=win32api.OpenProcess(win32con.PROCESS_SET_QUOTA|win32con.PROCESS_TERMINATE,False,int(process.processId()))
  try:win32job.AssignProcessToJobObject(job,handle)
  finally:handle.Close()
  self.jobs.append(job)
 def backend_output(self):
  output=bytes(self.backend.readAllStandardOutput()).decode(errors='replace')
  # Runtime logs remain local. Avoid retaining conversation text in a log file.
  if 'Traceback' in output or 'Error:' in output:self.skill.setToolTip('Jinx could not start. Open setup to check its dependencies.')
 def page_loaded(self,ok):
  self.loaded=ok
  if ok:self.publish_layout();self.platform_options(self.web)
 def platform_options(self,view):
  view.page().runJavaScript("for(const o of document.querySelectorAll('#voiceChoice option'))if(!['breeze_tts2','piper_alba'].includes(o.value))o.remove();for(const o of document.querySelectorAll('#speechEngine option'))if(o.value!=='cpu')o.remove();")
 def apply_layout(self):
  scale=max(.5,min(1.5,float(self.layout_state.get('scale',.85))))
  self.layout_state['scale']=scale;self.resize(round(532*scale),round(668*scale))
  area=QApplication.primaryScreen().availableGeometry()
  self.move(int(self.layout_state.get('x',area.center().x()-self.width()/2)),int(self.layout_state.get('y',area.bottom()-self.height()-12)))
  if self.web:self.web.setGeometry(self.rect())
  self.skill.move(self.width()-65,self.height()-68)
 def publish_layout(self):
  if self.web:self.web.page().runJavaScript('window.setNativeLayout?.('+json.dumps({**self.layout_state,'minScale':.5,'maxScale':1.5})+')')
 def persist(self):self.layout_state.update(x=self.x(),y=self.y());atomic(DATA/'avatar-layout.json',self.layout_state)
 def handle_native(self,raw):
  try:result=json.loads(raw or '{}')
  except (ValueError,TypeError):return
  active=bool(result.get('active'))
  if active!=self.top:
   self.top=active;self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,active);self.show()
  action=result.get('action')
  if action=='layout':self.publish_layout()
  elif action=='settings':self.settings()
  elif action=='sleep':self.sleep()
  elif action=='start':self.wake()
  elif isinstance(action,dict):
   kind=action.get('kind')
   if kind=='unlock':self.layout_state['unlocked']=bool(action['value']);self.persist();self.publish_layout()
   elif kind=='scale':self.layout_state['scale']=action['value'];self.apply_layout();self.publish_layout();self.persist()
   elif kind=='reset':self.layout_state={'scale':.85,'unlocked':False};self.apply_layout();self.persist();self.publish_layout()
   elif kind=='move' and self.layout_state.get('unlocked'):
    if self.drag_id!=action['id']:self.drag_id=action['id'];self.drag_start=self.pos()
    self.move(self.drag_start+QPoint(round(action['dx']),round(action['dy'])))
    if action.get('finished'):self.drag_id=None;self.persist()
 def tick(self):
  if self.web:
   if self.loaded:self.web.page().runJavaScript('JSON.stringify({action:window.consumeNativeAction?.(),active:window.jinxInteractionActive?.()})',self.handle_native)
   elif self.backend and self.backend.state()==QProcess.ProcessState.Running and time.monotonic()>self.next_reload:
    self.next_reload=time.monotonic()+3
    self.web.setUrl(QUrl(ORIGIN+'/avatar/index.html'))
  attention=RUNTIME/'jinx-attention'
  try:s=json.loads((attention/'state.json').read_text())
  except (OSError,ValueError):s={}
  if s.get('active') and s.get('expires',0)>time.time():
   self.corner.show();self.corner.update();self.corner.repaint()
   atomic(attention/'ready.json',{'id':s['id']})
  else:self.corner.hide()
  for p in (RUNTIME/'ui-requests').glob('*.json'):
   if p.name in self.requests:continue
   self.requests.add(p.name)
   try:
    request=json.loads(p.read_text());response={}
    if request['expires']<time.time():continue
    if request['kind']=='document':response={'path':QFileDialog.getOpenFileName(self,'Share a document with Jinx','','Documents (*.txt *.md *.csv *.log *.pdf *.docx *.odt)')[0]}
    elif request['kind']=='notification':
     f=request['fields'];self.tray.showMessage(str(f['title']),str(f['text']),QSystemTrayIcon.MessageIcon.Information,10000);response={'delivered':self.tray.isVisible() and QSystemTrayIcon.supportsMessages()}
    elif request['kind']=='settings':self.settings();response={'shown':self.work.isVisible()}
    else:response={'error':'Unknown desktop request'}
    atomic(p.with_suffix('.reply'),response)
   except Exception:atomic(p.with_suffix('.reply'),{'error':'The desktop action could not complete.'})
 def settings(self):
  if not self.backend:self.wake()
  if self.work is None:self.work=Workspace(self)
  self.work.show();self.work.raise_();self.work.activateWindow()
 def configure(self):
  if self.setup is None:self.setup=Setup(self)
  self.setup.show();self.setup.raise_();self.setup.activateWindow()
 def talk(self):
  if not self.backend:
   self.wake()
   if self.backend:QTimer.singleShot(1800,self.talk)
   return
  try:
   state=self.api('/status');self.api('/stop' if state.get('conversation') or state.get('busy') else '/conversation',{})
  except Exception:self.configure()
 def toggle(self):self.sleep() if self.backend else self.wake()
 def sleep(self):
  if self.backend:
   try:self.api('/stop',{})
   except Exception:pass
   self.backend.terminate()
   if not self.backend.waitForFinished(2500):self.backend.kill();self.backend.waitForFinished(1500)
   self.backend.deleteLater();self.backend=None
  if self.web:self.web.deleteLater();self.web=None
  if self.work:self.work.close();self.work.deleteLater();self.work=None
  if self.model_process:
   self.model_process.terminate()
   if not self.model_process.waitForFinished(1500):self.model_process.kill()
   self.model_process.deleteLater();self.model_process=None
  for job in self.jobs:job.Close()
  self.jobs.clear()
  self.corner.hide();self.loaded=False;self.top=False;self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,False);self.show();self.skill.setToolTip('Wake Jinx')
 def quit(self):self.closing=True;self.sleep();self.tray.hide();QApplication.quit()
 def closeEvent(self,event):
  if self.closing:event.accept()
  else:self.sleep();event.ignore()

def main():
 global TOKEN,DATA,RUNTIME
 smoke='--smoke-test' in sys.argv
 DATA.mkdir(parents=True,exist_ok=True);RUNTIME.mkdir(parents=True,exist_ok=True)
 key=DATA/'access.key'
 if not key.exists():key.write_text(secrets.token_urlsafe(32))
 TOKEN=key.read_text().strip()
 if not (DATA/'state.json').exists():atomic(DATA/'state.json',{'voice':'breeze_tts2','voice_speed':1,'speech_engine':'cpu','ai_mode':'local_fast','listening':False,'speak':True,'thinking_sounds':True,'memory':'','reminders':[],'pending':[]})
 app=QApplication(sys.argv);app.setQuitOnLastWindowClosed(False);app.setApplicationName('Jinx');app.setStyleSheet(STYLE)
 if '--notification-file' in sys.argv:
  try:
   path=Path(sys.argv[sys.argv.index('--notification-file')+1]).resolve()
   if path.parent!=(RUNTIME/'notifications').resolve() or not __import__('re').fullmatch(r'[a-f0-9]{24}\.json',path.name):return 1
   value=json.loads(path.read_text())
   if value.get('expires',0)<time.time():return 1
   tray=QSystemTrayIcon(QIcon(str(ASSETS/'jinx.ico')));tray.show()
   if not QSystemTrayIcon.supportsMessages():return 1
   QTimer.singleShot(250,lambda:tray.showMessage(str(value['title']),str(value['text']),QSystemTrayIcon.MessageIcon.Information,10000))
   QTimer.singleShot(10000,app.quit);result=app.exec();tray.hide();return result
  except Exception:return 1
 lock=None
 if not smoke:
  lock=QLockFile(str(RUNTIME/'desktop.lock'));lock.setStaleLockTime(0)
  if not lock.tryLock(0):
   QMessageBox.information(None,'Jinx is already open','Use the Jinx portrait or tray icon to start talking.');return 0
 window=Avatar(smoke)
 if not smoke and os.name=='nt':
  from hotkey import NativeEvents
  events=NativeEvents(window);app.installNativeEventFilter(events);app.aboutToQuit.connect(events.close)
 if smoke:
  window.web=window.webview(window);window.web.setGeometry(window.rect());window.web.show()
  # UI imports/rendering are tested without microphone, account credentials or model downloads.
  window.web.page().setProperty('smoke',True)
  window.web.setHtml('<html><body style="background:transparent">Jinx</body></html>',QUrl(ORIGIN+'/'))
  def check():
   def done(value):
    Path(os.environ.get('JINX_SMOKE_REPORT','windows-smoke.json')).write_text(json.dumps({'ui':bool(value),'shared_backend':(BUNDLE/'app/jinx.py').is_file(),'breeze_library':(BUNDLE/'voice/jinx-breeze.dll').is_file(),'speech_imports':True}))
    window.closing=True;window.tray.hide();app.exit(0 if value else 1)
   window.web.page().runJavaScript('document.body.textContent.includes("Jinx")',done)
  QTimer.singleShot(5000,check);QTimer.singleShot(40000,lambda:app.exit(1))
 app.aboutToQuit.connect(window.sleep)
 return app.exec()
if __name__=='__main__':raise SystemExit(main())
