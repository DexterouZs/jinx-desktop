#include <QGuiApplication>
#include <QDBusConnection>
#include <QQmlApplicationEngine>
#include <QQuickWindow>
#include <QQmlContext>
#include <QQuickWebEngineProfile>
#include <QtWebEngineQuick/qtwebenginequickglobal.h>
#include <QWebEngineUrlRequestInterceptor>
#include <QFile>
#include <QDir>
#include <QProcess>
#include <QTimer>
#include <QSettings>
#include <QQuickView>
#include <QFileSystemWatcher>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSaveFile>
#include <QDateTime>
#include <QScreen>
#include <QVariantMap>
#include <cmath>
#include <QLockFile>
#include <LayerShellQt/Window>
class LocalOnly : public QWebEngineUrlRequestInterceptor {
 QByteArray token;
 public:LocalOnly(QObject *p):QWebEngineUrlRequestInterceptor(p){QFile f(QDir::homePath()+"/.local/state/jinx/access.key");if(f.open(QIODevice::ReadOnly))token=f.readAll().trimmed();}
 void interceptRequest(QWebEngineUrlRequestInfo &info) override {
  auto u=info.requestUrl();
  if(u.scheme()=="data"||u.scheme()=="blob"||u.scheme()=="about")return;
  if(u.scheme()!="http"||u.host()!="127.0.0.1"||u.port()!=17341){info.block(true);return;}
  info.setHttpHeader("X-Jinx-Token",token);
 }
};
class Controls:public QObject {
 Q_OBJECT
 Q_CLASSINFO("D-Bus Interface", "org.jinx.Desktop")
 Q_PROPERTY(bool sleeping READ sleeping NOTIFY sleepChanged)
 Q_PROPERTY(bool sleepPending READ sleepPending NOTIFY sleepChanged)
 Q_PROPERTY(bool interactionActive READ interactionActive NOTIFY interactionChanged)
 bool foreground=false;
 bool asleep=false,changingSleep=false;
 QQuickWindow *window=nullptr;
 LayerShellQt::Window *layer=nullptr;
 QSettings settings{QDir::homePath()+"/.config/jinx-avatar.ini",QSettings::IniFormat};
 double scale=1, nx=.5, ny=-1;
 int left=0,top=0;
 QString dragId;
 bool unlocked=false;
 QSize screenSize() const {return window&&window->screen()?window->screen()->geometry().size():QSize(1707,1067);}
 double baseHeight() const {return .70*qMin(980,screenSize().height()-112);}
 void remember() {
  settings.setValue("scale",scale);settings.setValue("x",nx);settings.setValue("y",ny);settings.sync();
 }
 void place(int x,int y) {
  if(!window)return;
  auto screen=screenSize();left=qBound(0,x,qMax(0,screen.width()-window->width()));top=qBound(32,y,qMax(32,screen.height()-window->height()));
  nx=double(left)/qMax(1,screen.width()-window->width());ny=double(top)/qMax(1,screen.height()-window->height());
  layer->setMargins(QMargins(left,top,0,0));emit layoutChanged();
 }
 void resizeAt(double centre,double bottom) {
  auto screen=screenSize();double maximum=qMin(1.6,(screen.height()-48)/baseHeight());
  scale=qBound(qMax(.4,260/baseHeight()),scale,maximum);
  int h=qRound(baseHeight()*scale),w=qRound(h*780.0/980.0);
  window->resize(w,h);layer->setDesiredSize(QSize(w,h));
  place(qRound(centre-w/2.0),qRound(bottom-h));
 }
 public:
 Controls(){
  asleep=QFile::exists(qEnvironmentVariable("XDG_RUNTIME_DIR")+"/jinx-skull-sleep.json");
  if(asleep)QTimer::singleShot(0,this,[](){QProcess::startDetached("/usr/bin/python3",{QDir::homePath()+"/Jinx/sleep_control.py","sleep"});});
 }
 bool interactionActive()const{return foreground;}
 Q_INVOKABLE void setInteractionActive(bool value){
  value=value&&!asleep;
  if(foreground==value)return;foreground=value;
  if(layer)layer->setLayer(value?LayerShellQt::Window::LayerOverlay:LayerShellQt::Window::LayerBottom);
  emit interactionChanged();
 }
 bool sleeping()const{return asleep;}
 bool sleepPending()const{return changingSleep;}
 Q_INVOKABLE void toggleSleep(){
  if(changingSleep)return;changingSleep=true;emit sleepChanged();
  auto *process=new QProcess(this);const bool next=!asleep;
  connect(process,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,[this,process](int,QProcess::ExitStatus){changingSleep=false;asleep=QFile::exists(qEnvironmentVariable("XDG_RUNTIME_DIR")+"/jinx-skull-sleep.json");if(asleep)setInteractionActive(false);emit sleepChanged();process->deleteLater();});
  connect(process,&QProcess::errorOccurred,this,[this,process](QProcess::ProcessError error){if(error==QProcess::FailedToStart){changingSleep=false;emit sleepChanged();process->deleteLater();}});
  process->start("/usr/bin/python3",{QDir::homePath()+"/Jinx/sleep_control.py",next?"sleep":"wake"});
 }
 void attach(QQuickWindow *w,LayerShellQt::Window *l) {
  window=w;layer=l;
  scale=settings.value("scale",1).toDouble();nx=settings.value("x",.5).toDouble();ny=settings.value("y",-1).toDouble();
  if(!std::isfinite(scale))scale=1;if(!std::isfinite(nx))nx=.5;if(!std::isfinite(ny))ny=-1;
  layer->setAnchors(LayerShellQt::Window::Anchors(LayerShellQt::Window::AnchorTop|LayerShellQt::Window::AnchorLeft));
  auto screen=screenSize();int h=qRound(baseHeight()*qBound(.4,scale,1.6)),width=qRound(h*780.0/980.0);
  double x=qBound(0.0,nx,1.0)*qMax(0,screen.width()-width),y=ny<0?screen.height()-h-72:qBound(0.0,ny,1.0)*qMax(0,screen.height()-h);
  resizeAt(x+width/2.0,y+h);
  connect(window->screen(),&QScreen::geometryChanged,this,[this](){auto screen=screenSize();resizeAt(nx*qMax(0,screen.width()-window->width())+window->width()/2.0,ny*qMax(0,screen.height()-window->height())+window->height());});
 }
 Q_INVOKABLE QVariantMap layout() const {
  QVariantMap idleLoop;
  for(const auto &key: {"interaction","restAfter","sleepAfter","blinkEvery","blinkFor","activeFPS","idleFPS","restFPS"}) {
   const auto path=QString("idleLoop/")+key;
   if(settings.contains(path))idleLoop.insert(key,settings.value(path));
  }
  return {{"idleLoop",idleLoop},{"scale",scale},{"unlocked",unlocked},{"x",left},{"y",top},{"width",window?window->width():0},{"height",window?window->height():0},{"screenWidth",screenSize().width()},{"screenHeight",screenSize().height()},{"minScale",qMax(.4,260/baseHeight())},{"maxScale",qMin(1.6,(screenSize().height()-48)/baseHeight())}};
 }
 Q_INVOKABLE void setUnlocked(bool value){unlocked=value;dragId.clear();if(!unlocked)remember();emit layoutChanged();}
 Q_INVOKABLE void setScale(double value,bool persist){if(!window||!std::isfinite(value))return;scale=value;resizeAt(left+window->width()/2.0,top+window->height());if(persist)remember();}
 Q_INVOKABLE void moveAvatar(double dx,double dy,QString id,bool finished){
  if(!unlocked||!window||!std::isfinite(dx)||!std::isfinite(dy))return;
  dragId=id;
  // Layer-shell does not expose global window coordinates on Wayland.
  // Move by the pointer displacement from its fixed local grab point.
  place(left+qRound(qBound(-10000.0,dx,10000.0)),top+qRound(qBound(-10000.0,dy,10000.0)));
  if(finished)remember();
 }
 Q_INVOKABLE void resetLayout(){scale=1;unlocked=false;dragId.clear();auto screen=screenSize();resizeAt(screen.width()/2.0,screen.height()-72);remember();emit layoutChanged();}
 Q_INVOKABLE void openSettings(){QProcess::startDetached(QDir::homePath()+"/.local/bin/jinx",{"open"});}
 Q_INVOKABLE void startBackend(){QProcess::startDetached("/usr/bin/systemctl",{"--user","start","jinx.service"});}
 signals:void layoutChanged();void sleepChanged();void interactionChanged();
};
class Attention:public QObject {
 Q_OBJECT
 Q_PROPERTY(bool active READ active NOTIFY changed)
 bool enabled=false;QString identifier,path;double expires=0;
 QFileSystemWatcher watcher;QTimer expiry;
 public:
 Attention(){
  path=qEnvironmentVariable("XDG_RUNTIME_DIR")+"/jinx-attention";QDir().mkpath(path);
  watcher.addPath(path);connect(&watcher,&QFileSystemWatcher::directoryChanged,this,[this](){refresh();});
  expiry.setInterval(1000);connect(&expiry,&QTimer::timeout,this,[this](){if(QDateTime::currentMSecsSinceEpoch()/1000.0>expires){enabled=false;expiry.stop();emit changed();}});
  refresh();
 }
 bool active()const{return enabled;}
 void refresh(){
  QFile file(path+"/state.json");QJsonObject value;if(file.open(QIODevice::ReadOnly))value=QJsonDocument::fromJson(file.readAll()).object();
  expires=value["expires"].toDouble();bool next=value["active"].toBool()&&expires>QDateTime::currentMSecsSinceEpoch()/1000.0;
  QString nextId=value["id"].toString();bool notify=next!=enabled||nextId!=identifier;enabled=next;identifier=nextId;
  if(enabled)expiry.start();else expiry.stop();if(notify)emit changed();
 }
 void acknowledge(){
  if(!enabled)return;
  QFile previous(path+"/ready.json");if(previous.open(QIODevice::ReadOnly)&&QJsonDocument::fromJson(previous.readAll()).object()["id"].toString()==identifier)return;
  QSaveFile file(path+"/ready.json");if(file.open(QIODevice::WriteOnly)){file.setPermissions(QFileDevice::ReadOwner|QFileDevice::WriteOwner);file.write(QJsonDocument(QJsonObject{{"id",identifier}}).toJson());file.commit();}
 }
 signals:void changed();
};
int main(int argc,char **argv){
 QtWebEngineQuick::initialize();
 QGuiApplication app(argc,argv);app.setApplicationName("Jinx Desktop");app.setDesktopFileName("jinx-widget");
 QLockFile single(qEnvironmentVariable("XDG_RUNTIME_DIR")+"/jinx-desktop.lock");if(!single.tryLock(100))return 0;
 auto *profile=QQuickWebEngineProfile::defaultProfile();profile->setOffTheRecord(true);
 LocalOnly filter(&app);profile->setUrlRequestInterceptor(&filter);
 QQmlApplicationEngine engine;Controls controls;engine.rootContext()->setContextProperty("nativeControls",&controls);
 QDBusConnection::sessionBus().registerService("org.jinx.Desktop");
 QDBusConnection::sessionBus().registerObject("/org/jinx/Desktop",&controls,QDBusConnection::ExportAllInvokables|QDBusConnection::ExportAllProperties);
 engine.load(QUrl::fromLocalFile(QDir::homePath()+"/Jinx/avatar3d/native/main.qml"));if(engine.rootObjects().isEmpty())return 1;
 auto *window=qobject_cast<QQuickWindow*>(engine.rootObjects().first());if(!window)return 2;
 auto *layer=LayerShellQt::Window::get(window);layer->setLayer(LayerShellQt::Window::LayerBottom);
 controls.attach(window,layer);layer->setExclusiveZone(-1);
 layer->setKeyboardInteractivity(LayerShellQt::Window::KeyboardInteractivityOnDemand);
 layer->setActivateOnShow(false);layer->setScope("jinx-desktop");window->show();
 Attention attention;
 auto addGlow=[&](QScreen *screen){
  auto *view=new QQuickView;view->setScreen(screen);view->setColor(Qt::transparent);
  view->setFlags(Qt::FramelessWindowHint|Qt::Tool|Qt::WindowTransparentForInput|Qt::WindowDoesNotAcceptFocus);
  view->setResizeMode(QQuickView::SizeRootObjectToView);view->rootContext()->setContextProperty("attention",&attention);
  view->setTitle("Jinx screen activity");auto *surface=LayerShellQt::Window::get(view);
  surface->setLayer(LayerShellQt::Window::LayerOverlay);surface->setScope("jinx-screen-attention");surface->setExclusiveZone(-1);
  surface->setAnchors(LayerShellQt::Window::Anchors(LayerShellQt::Window::AnchorTop|LayerShellQt::Window::AnchorBottom|LayerShellQt::Window::AnchorLeft|LayerShellQt::Window::AnchorRight));
  surface->setKeyboardInteractivity(LayerShellQt::Window::KeyboardInteractivityNone);surface->setActivateOnShow(false);
  view->resize(screen->size());surface->setDesiredSize(screen->size());
  view->setSource(QUrl::fromLocalFile(QDir::homePath()+"/Jinx/avatar3d/native/attention.qml"));
  QObject::connect(&attention,&Attention::changed,view,[view,&attention](){if(attention.active())view->show();});
  QObject::connect(view,&QQuickWindow::frameSwapped,&attention,[&attention](){attention.acknowledge();});
  QObject::connect(screen,&QScreen::geometryChanged,view,[view,surface,screen](){view->resize(screen->size());surface->setDesiredSize(screen->size());});
  QObject::connect(screen,&QObject::destroyed,view,&QObject::deleteLater);
  if(attention.active())view->show();
 };
 for(auto *screen:app.screens())addGlow(screen);
 QObject::connect(&app,&QGuiApplication::screenAdded,&app,addGlow);
 return app.exec();
}
#include "main.moc"
