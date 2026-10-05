// SPDX-License-Identifier: MIT
// QTBUG-151052: public Qt APIs only. --portal runs a private failure fixture.
#include <QCoreApplication>
#include <QGuiApplication>
#include <QDBusArgument>
#include <QDBusConnection>
#include <QDBusError>
#include <QDBusMessage>
#include <QDBusMetaType>
#include <QDBusObjectPath>
#include <QDBusVariant>
#include <QDBusVirtualObject>
#include <QEventLoop>
#include <QMediaCaptureSession>
#include <QScreenCapture>
#include <QTextStream>
#include <QTimer>
#include <QVideoSink>

struct Stream { uint node; QVariantMap properties; };
using Streams = QList<Stream>;
Q_DECLARE_METATYPE(Stream)
Q_DECLARE_METATYPE(Streams)
QDBusArgument &operator<<(QDBusArgument &arg, const Stream &stream)
{
    arg.beginStructure(); arg << stream.node << stream.properties; arg.endStructure();
    return arg;
}
const QDBusArgument &operator>>(const QDBusArgument &arg, Stream &stream)
{
    arg.beginStructure(); arg >> stream.node >> stream.properties; arg.endStructure();
    return arg;
}

class Portal : public QDBusVirtualObject
{
public:
    QString introspect(const QString &) const override
    {
        return QStringLiteral(R"XML(
<interface name="org.freedesktop.portal.ScreenCast">
  <property name="version" type="u" access="read"/>
  <method name="CreateSession"><arg type="a{sv}" direction="in"/><arg type="o" direction="out"/></method>
  <method name="SelectSources"><arg type="o" direction="in"/><arg type="a{sv}" direction="in"/><arg type="o" direction="out"/></method>
  <method name="Start"><arg type="o" direction="in"/><arg type="s" direction="in"/><arg type="a{sv}" direction="in"/><arg type="o" direction="out"/></method>
  <method name="OpenPipeWireRemote"><arg type="o" direction="in"/><arg type="a{sv}" direction="in"/><arg type="h" direction="out"/></method>
</interface>)XML");
    }
    bool handleMessage(const QDBusMessage &message, const QDBusConnection &bus) override
    {
        const auto member = message.member();
        if (message.interface() == "org.freedesktop.DBus.Properties" && member == "Get") {
            bus.send(message.createReply(QVariant::fromValue(QDBusVariant(uint(4)))));
            return true;
        }
        if (message.interface() == "org.freedesktop.portal.Session" && member == "Close") {
            bus.send(message.createReply());
            return true;
        }
        if (message.interface() != "org.freedesktop.portal.ScreenCast")
            return false;
        if (member == "OpenPipeWireRemote") {
            QTextStream(stdout) << "Injecting OpenPipeWireRemote failure" << Qt::endl;
            bus.send(message.createErrorReply("org.freedesktop.portal.Error.Failed",
                                               "Synthetic remote failure"));
            return true;
        }
        QVariantMap values;
        if (member == "CreateSession") {
            values.insert("session_handle", QString("/org/freedesktop/portal/desktop/session/test"));
        } else if (member == "Start") {
            QDBusArgument size;
            size.beginStructure(); size << 640 << 480; size.endStructure();
            QVariantMap properties{{"size", QVariant::fromValue(size)}, {"source_type", uint(1)}};
            values.insert("streams", QVariant::fromValue(Streams{{123, properties}}));
        } else if (member != "SelectSources") {
            return false;
        }
        // Honor handle_token: newer Qt subscribes before making the request.
        const auto options = qdbus_cast<QVariantMap>(message.arguments().last());
        QString sender = message.service().mid(1);
        sender.replace('.', '_');
        const QString token = options.value("handle_token", QString("r%1").arg(++request)).toString();
        const QString path = "/org/freedesktop/portal/desktop/request/" + sender + "/" + token;
        bus.send(message.createReply(QVariant::fromValue(QDBusObjectPath(path))));
        QTimer::singleShot(20, this, [bus, path, values] {
            auto response = QDBusMessage::createSignal(path, "org.freedesktop.portal.Request", "Response");
            response << uint(0) << values;
            bus.send(response);
        });
        return true;
    }
private:
    int request = 0;
};

int main(int argc, char **argv)
{
    if (argc == 2 && QByteArray(argv[1]) == "--portal") {
        QCoreApplication app(argc, argv);
        qDBusRegisterMetaType<Stream>();
        qDBusRegisterMetaType<Streams>();
        auto bus = QDBusConnection::sessionBus();
        Portal portal;
        if (!bus.registerService("org.freedesktop.portal.Desktop") ||
            !bus.registerVirtualObject("/org/freedesktop/portal/desktop", &portal, QDBusConnection::SubPath)) {
            QTextStream(stderr) << bus.lastError().message() << Qt::endl;
            return 2;
        }
        QTextStream(stdout) << "ready" << Qt::endl;
        return app.exec();
    }
    QGuiApplication app(argc, argv);
    QTextStream(stdout) << "Qt " << qVersion() << ": C++ public-API cleanup probe" << Qt::endl;
    for (int attempt = 1; attempt <= 20; ++attempt) {
        QMediaCaptureSession session;
        QScreenCapture capture;
        QVideoSink sink;
        session.setScreenCapture(&capture);
        session.setVideoSink(&sink);
        QEventLoop wait;
        QStringList errors;
        QObject::connect(&capture, &QScreenCapture::errorOccurred, &wait,
                         [&](QScreenCapture::Error, const QString &message) {
            errors.append(message);
            wait.quit();
        }, Qt::QueuedConnection);
        QTimer timeout;
        timeout.setSingleShot(true);
        QObject::connect(&timeout, &QTimer::timeout, &wait, &QEventLoop::quit);
        timeout.start(5000);
        capture.start();
        wait.exec();
        QTextStream(stdout) << "Cycle " << attempt << ": " << errors.join(" | ") << Qt::endl;
        if (errors.size() != 1 || !errors.first().contains("Synthetic remote failure")) {
            QTextStream(stderr) << "Expected injected failure was not observed; test is inconclusive." << Qt::endl;
            return 2;
        }
        QTextStream(stdout) << "Stopping capture through its public API" << Qt::endl;
        capture.stop();
        session.setScreenCapture(nullptr);
        session.setVideoSink(nullptr);
    }
    QTextStream(stdout) << "20 failed-initialization/cleanup cycles passed" << Qt::endl;
    return 0;
}
