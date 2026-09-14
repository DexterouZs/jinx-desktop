#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickWindow>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QFile>
#include <QSaveFile>
#include <QDir>
#include <QTimer>
#include <QScreen>
#include <QRegularExpression>
#include <QLockFile>
#include <LayerShellQt/Window>

class Installer:public QObject {
 Q_OBJECT
 Q_PROPERTY(QString title READ title NOTIFY changed)
 Q_PROPERTY(QString review READ review NOTIFY changed)
 Q_PROPERTY(QString message READ message NOTIFY changed)
 Q_PROPERTY(bool actionable READ actionable NOTIFY changed)
 Q_PROPERTY(bool hidden READ hidden NOTIFY changed)
 Q_PROPERTY(bool finished READ finished NOTIFY changed)
 QString id,token,label="Install application",details,notice="Loading the installation preview…",jobState;
 bool canInstall=false,hide=false,done=false,requestPending=false,submitting=false;
 QNetworkAccessManager network;QTimer poll;
 public:
 Installer(QString identifier):id(identifier){
  QFile key(QDir::homePath()+"/.local/state/jinx/access.key");if(key.open(QIODevice::ReadOnly))token=QString::fromUtf8(key.readAll()).trimmed();
  poll.setInterval(500);connect(&poll,&QTimer::timeout,this,&Installer::refresh);poll.start();QTimer::singleShot(0,this,&Installer::refresh);
 }
 QString title()const{return label;}QString review()const{return details;}QString message()const{return notice;}
 bool actionable()const{return canInstall&&!submitting;}bool hidden()const{return hide;}bool finished()const{return done;}
 void acknowledged(){
  if(!canInstall||hide)return;
  QString path=qEnvironmentVariable("XDG_RUNTIME_DIR")+"/jinx-install-review";QDir().mkpath(path);
  QSaveFile file(path+"/"+id+".ready");if(file.open(QIODevice::WriteOnly)){file.write(QJsonDocument(QJsonObject{{"pid",double(QCoreApplication::applicationPid())}}).toJson());file.commit();}
 }
 QNetworkRequest request(QString path){QNetworkRequest r(QUrl("http://127.0.0.1:17341"+path));r.setRawHeader("X-Jinx-Token",token.toUtf8());r.setHeader(QNetworkRequest::ContentTypeHeader,"application/json");r.setTransferTimeout(15000);return r;}
 Q_INVOKABLE void refresh(){
  if(requestPending||submitting)return;requestPending=true;
  auto *reply=network.get(request("/status"));
  connect(reply,&QNetworkReply::finished,this,[this,reply](){
   requestPending=false;auto root=QJsonDocument::fromJson(reply->readAll()).object();bool failed=reply->error()!=QNetworkReply::NoError;reply->deleteLater();
   if(failed){notice="Jinx is unavailable. Please reopen the installer when she is running.";hide=false;canInstall=false;emit changed();return;}
   QJsonObject proposal,job;
   for(auto value:root["pending"].toArray()){auto p=value.toObject();if(p["id"].toString()==id&&p["kind"].toString()=="software_install")proposal=p;}
   for(auto value:root["software_installs"].toArray()){auto p=value.toObject();if(p["proposal_id"].toString()==id){job=p;break;}}
   if(!job.isEmpty()){
    jobState=job["state"].toString();notice=job["message"].toString();canInstall=false;
    done=jobState=="installed"||jobState=="failed"||jobState=="cancelled";
    // Get out of the way of the trusted KDE authentication dialogue.
    hide=!done;
   }else if(!proposal.isEmpty()){
    auto fields=proposal["fields"].toObject();auto name=fields["knowledge"].toObject()["name"].toString(fields["package"].toString());
    label="Install "+name;details=fields["review"].toString();canInstall=true;hide=false;done=false;
    notice=!fields["install_kind"].toString().isEmpty() ? "Click Install to add this to your user account. No administrator password needed." : "Click Install, or tell Jinx “yes, install it”. KDE handles authentication.";
   }else {canInstall=false;done=true;hide=false;notice="This installation preview is no longer pending.";}
   emit changed();
  });
 }
 Q_INVOKABLE void install(){
  if(!actionable())return;submitting=true;hide=true;notice="Starting the installer…";emit changed();
  auto *reply=network.post(request("/confirm"),QJsonDocument(QJsonObject{{"id",id}}).toJson());
  connect(reply,&QNetworkReply::finished,this,[this,reply](){
   auto data=QJsonDocument::fromJson(reply->readAll()).object();bool failed=reply->error()!=QNetworkReply::NoError;reply->deleteLater();submitting=false;
   if(failed){notice=data["error"].toString("Installation could not start.");hide=false;canInstall=false;done=true;poll.stop();emit changed();}else refresh();
  });
 }
 Q_INVOKABLE void cancel(){
  if(!canInstall){QCoreApplication::quit();return;}
  auto *reply=network.post(request("/reject"),QJsonDocument(QJsonObject{{"id",id}}).toJson());
  connect(reply,&QNetworkReply::finished,this,[reply](){reply->deleteLater();QCoreApplication::quit();});
 }
 Q_INVOKABLE void close(){QCoreApplication::quit();}
 signals:void changed();
};
int main(int argc,char **argv){
 QGuiApplication app(argc,argv);app.setApplicationName("Jinx Installer");
 if(argc!=2||!QRegularExpression("^[a-f0-9]{16}$").match(argv[1]).hasMatch())return 2;
 QString id=argv[1];QLockFile lock(qEnvironmentVariable("XDG_RUNTIME_DIR")+"/jinx-installer-"+id+".lock");if(!lock.tryLock(100))return 0;
 Installer installer(id);QQmlApplicationEngine engine;engine.rootContext()->setContextProperty("installer",&installer);
 engine.load(QUrl::fromLocalFile(QDir::homePath()+"/Jinx/installer/main.qml"));if(engine.rootObjects().isEmpty())return 3;
 auto *window=qobject_cast<QQuickWindow*>(engine.rootObjects().first());if(!window)return 4;
 window->resize(qMin(560,app.primaryScreen()->size().width()-40),qMin(660,app.primaryScreen()->size().height()-80));
 auto *layer=LayerShellQt::Window::get(window);layer->setLayer(LayerShellQt::Window::LayerOverlay);layer->setAnchors({});layer->setExclusiveZone(-1);layer->setScope("jinx-install-review");layer->setActivateOnShow(true);layer->setKeyboardInteractivity(LayerShellQt::Window::KeyboardInteractivityOnDemand);
 QObject::connect(&installer,&Installer::changed,window,[&installer,window,id](){if(installer.hidden()){window->hide();QFile::remove(qEnvironmentVariable("XDG_RUNTIME_DIR")+"/jinx-install-review/"+id+".ready");}else window->show();});
 QObject::connect(&app,&QCoreApplication::aboutToQuit,[id](){QFile::remove(qEnvironmentVariable("XDG_RUNTIME_DIR")+"/jinx-install-review/"+id+".ready");});
 QObject::connect(window,&QQuickWindow::frameSwapped,&installer,&Installer::acknowledged);window->show();return app.exec();
}
#include "main.moc"
