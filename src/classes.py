#!/usr/bin/env python2.7
# *-* coding: utf-8 *-*

import dbus
from Queue import PriorityQueue
from threading import Lock
from PyQt4 import QtCore, QtGui, QtSvg
from src.constants import *
from src.utils import *

class DBusNotificationsManager(QtCore.QObject):
    finished = QtCore.pyqtSignal()

    def __init__(self, main):
        QtCore.QObject.__init__(self)
        self.main = main
        self.queue = PriorityQueue()
        self.idqueue = []
        self.lock = Lock()
        self.proxy = dbus.SessionBus().get_object('org.freedesktop.Notifications', '/org/freedesktop/Notifications')
        self.iface = dbus.Interface(self.proxy, dbus_interface='org.freedesktop.Notifications')
#        self.iface.connect_to_signal('NotificationClosed', self.notificationClosed)
        self.closeTimer = QtCore.QTimer()
        self.closeTimer.setSingleShot(True)
        self.closeTimer.setInterval(5000)
        self.closeTimer.timeout.connect(self.closeNotification)

    def closeNotification(self):
        if not self.idqueue:
            self.lock.release() if self.lock.locked() else None
            return
        while self.idqueue:
#            print 'chiudo'
            self.iface.CloseNotification(self.idqueue.pop(0))
        self.lock.release() if self.lock.locked() else None

    def notificationClosed(self, id, reason):
        self.idqueue.pop(self.idqueue.index(id))
        self.lock.release() if self.lock.locked() else None

    def run(self):
        while True:
            p, res = self.queue.get()
            if res == -1:
                break
            if p == HIGH:
                if self.lock.locked():
                    self.closeTimer.stop()
                    self.lock.release()
#                    self.closeNotification()
            self.lock.acquire()
            title, body, icon, timeout = res
            try:
                id = self.iface.Notify('KdeConnectTray', 0, icon, title, body, [], {}, 0)
                if id not in self.idqueue:
                    self.idqueue.append(id)
            except dbus.exceptions.DBusException as e:
                print 'DBus exception?', e
                self.iface = dbus.Interface(self.proxy, dbus_interface='org.freedesktop.Notifications')
                id = self.iface.Notify('KdeConnectTray', 0, icon, title, body, [], {}, 0)
                if id not in self.idqueue:
                    self.idqueue.append(id)
            self.closeTimer.setInterval(timeout)
            self.closeTimer.start()
        self.lock.release() if self.lock.locked() else None
        self.closeNotification()
        self.finished.emit()

    def notify(self, title='KdeConnectTray', body='', icon=True, timeout=5000, priority=LOW):
        if not QtCore.QSettings().value('desktopNotifications', True).toBool():
            print 'bobbou'
            return
        if isinstance(icon, bool):
            icon = stateIcons[icon]
        elif icon.startswith('/') or icon.endswith('.png'):
            icon = 'file://' + icon
        self.queue.put((priority, (title, body, icon, timeout)))

    def quit(self):
        self.queue.put((0, -1))


class HighBatteryAlertValidator(QtGui.QRegExpValidator):
    def __init__(self, *args, **kwargs):
        self.mask = QtCore.QRegExp(r'^(([5-9]\d),){0,8}([5-9]\d)$')
        QtGui.QValidator.__init__(self, self.mask, *args, **kwargs)
        self.intermediate = QtCore.QRegExp(r'^([5-9]\d{0,1}){0,8}([5-9]\d{0,1})$')

    def validate(self, text, pos):
        res = QtGui.QRegExpValidator.validate(self, text, pos)
        if res:
            return res
        if not res and self.intermediate.exactMatch(text):
            return self.Intermediate, text, pos


class LowBatteryAlertValidator(QtGui.QRegExpValidator):
    def __init__(self, *args, **kwargs):
        self.mask = QtCore.QRegExp(r'^(([0-4]{0,1}\d|50),){0,8}(([0-4]{0,1}\d|50))$')
        QtGui.QValidator.__init__(self, self.mask, *args, **kwargs)


class QSettings(QtCore.QSettings):
    changed = QtCore.pyqtSignal(object, object)

    def setValue(self, key, value):
        self.changed.emit(self.group(), key)
        QtCore.QSettings.setValue(self, key, value)

    def remove(self, key):
        self.changed.emit(self.group(), key)
        QtCore.QSettings.remove(self, key)


class OnlineLed(QtGui.QPixmap):
    def __init__(self):
        QtGui.QPixmap.__init__(self, QtCore.QSize(12, 12))
        self.fill(QtGui.QColor(255, 255, 255, 0))
        qp = QtGui.QPainter(self)
        qp.setRenderHints(qp.Antialiasing)
        qp.translate(.5, .5)
        grad = QtGui.QRadialGradient(5.5, 5.5, 5, 3.75, 3.75)
        grad.setColorAt(0, QtCore.Qt.white)
        grad.setColorAt(1, QtGui.QColor(0, 175, 0))
        qp.setPen(QtCore.Qt.darkGray)
        qp.setBrush(grad)
        qp.drawEllipse(0, 0, 11, 11)
        qp.end


class OfflineLed(QtGui.QPixmap):
    def __init__(self):
        QtGui.QPixmap.__init__(self, QtCore.QSize(12, 12))
        self.fill(QtGui.QColor(255, 255, 255, 0))
        qp = QtGui.QPainter(self)
        qp.setRenderHints(qp.Antialiasing)
        qp.translate(.5, .5)
        grad = QtGui.QRadialGradient(5.5, 5.5, 5, 3.75, 3.75)
        grad.setColorAt(0, QtCore.Qt.white)
        grad.setColorAt(1, QtGui.QColor(200, 0, 0))
        qp.setPen(QtCore.Qt.darkGray)
        qp.setBrush(grad)
        qp.drawEllipse(0, 0, 11, 11)
        qp.end


class Notification(QtCore.QObject):
    def __init__(self, phone, id):
        QtCore.QObject.__init__(self)
        self.phone = phone
        self.dbus = phone.dbus
        self.id = int(id)
        self.proxy = self.dbus.get_object('org.kde.kdeconnect', '/modules/kdeconnect/devices/{}/notifications/{}'.format(self.phone.id, self.id))
#        props = dbus.Interface(self.proxy, dbus_interface='org.kde.kdeconnect.device.notifications.notification')
        self.propsIface = dbus.Interface(self.proxy, dbus_interface='org.freedesktop.DBus.Properties')
        self.app = unicode(self.propsIface.Get('org.kde.kdeconnect.device.notifications.notification', 'appName'))
        self.ticker = unicode(self.propsIface.Get('org.kde.kdeconnect.device.notifications.notification', 'ticker'))
#        print self.ticker, self.app
        self.dismissable = self.propsIface.Get('org.kde.kdeconnect.device.notifications.notification', 'dismissable')

    @property
    def time(self):
        try:
            return self._time
        except:
            self._time = QtCore.QDateTime.currentMSecsSinceEpoch() / 1000

    @time.setter
    def time(self, time):
        self._time = time

    def dismiss(self):
        if not self.dismissable:
            return
        dbus.Interface(self.proxy, dbus_interface='org.kde.kdeconnect.device.notifications.notification').dismiss()
        self.deleteLater()

    def __repr__(self):
        return u'{}: ({}) {}'.format(self.id, self.app, self.ticker)


class NotificationDict(dict):
    def __init__(self, phone):
        super(NotificationDict, self).__init__()
        self.phone = phone

    def __getitem__(self, key):
        d = super(NotificationDict, self).keys()
        for k in map(int, (self.phone.notificationIface.activeNotifications())):
            if k not in d:
                try:
                    super(NotificationDict, self).pop(k)
                except:
                    pass
        return super(NotificationDict, self).__getitem__(key)

    def __setitem__(self, key, value):
        super(NotificationDict, self).__setitem__(key, value)

    def __delitem__(self, key):
        super(NotificationDict, self).__delitem__(key)


class Device(QtCore.QObject):
    reachableChanged = QtCore.pyqtSignal(bool)
    batteryChanged = QtCore.pyqtSignal(int)
    chargeStateChanged = QtCore.pyqtSignal(bool)
    notificationsChanged = QtCore.pyqtSignal()
    newNotification = QtCore.pyqtSignal(object)
    missingRequiredPlugin = QtCore.pyqtSignal(bool)
    pluginsChanged = QtCore.pyqtSignal()

    def __init__(self, deviceID):
        QtCore.QObject.__init__(self)
        self.id = deviceID
        self._reachable = False
        self._battery = 0
        self.batteryAlert = 15
        self._charging = False
        self.name = ''
        self.proxy = None
        self.propsIface = None
        self.devIface = None
        self.batteryIface = None
        self.notificationIface = None
        self._notifications = NotificationDict(self)
        self.loadedPlugins = []

    def setProxy(self, bus):
        self.dbus = bus
        self.proxy = self.dbus.get_object('org.kde.kdeconnect', '/modules/kdeconnect/devices/{}'.format(self.id))
        self.propsIface = dbus.Interface(self.proxy, dbus_interface='org.freedesktop.DBus.Properties')

        self.devIface = dbus.Interface(self.proxy, dbus_interface='org.kde.kdeconnect.device')
        self.devIface.connect_to_signal('reachableStatusChanged', lambda: self.setReachable(self.propsIface.Get('org.kde.kdeconnect.device', 'isReachable')))
        self.devIface.connect_to_signal('pluginsChanged', self.pluginsChangedCheck)
#            self.phoneDeviceProps.connect_to_signal('PropertiesChanged', self.reachable)
        self.batteryIface = dbus.Interface(self.proxy, dbus_interface='org.kde.kdeconnect.device.battery')
        self.batteryIface.connect_to_signal('chargeChanged', self.setBattery)
        self.batteryIface.connect_to_signal('stateChanged', self.setCharging)

        self.notificationIface = dbus.Interface(self.proxy, dbus_interface='org.kde.kdeconnect.device.notifications')
        self.notificationIface.connect_to_signal('notificationPosted', self.notificationPosted)
        self.notificationIface.connect_to_signal('notificationRemoved', self.notificationRemoved)
        self.notificationIface.connect_to_signal('allNotificationsRemoved', self.allNotificationsRemoved)

        self.findMyPhoneIface = dbus.Interface(
            self.dbus.get_object('org.kde.kdeconnect', '/modules/kdeconnect/devices/{}/findmyphone'.format(self.id)), 
            dbus_interface='org.kde.kdeconnect.device.findmyphone')

        self.shareIface = dbus.Interface(
            self.dbus.get_object('org.kde.kdeconnect', '/modules/kdeconnect/devices/{}/share'.format(self.id)), 
            dbus_interface='org.kde.kdeconnect.device.share')

        self.reachable = self.propsIface.Get('org.kde.kdeconnect.device', 'isReachable')
        self.name = self.propsIface.Get('org.kde.kdeconnect.device', 'name')
        self.battery = self.batteryIface.charge()
        self.charging = self.batteryIface.isCharging()
        self.createNotifications()

    def hasPlugin(self, plugin):
        if self.devIface is None:
            print 'staocazzoi'
            raise
        return self.devIface.hasPlugin(plugin)

    def hasMissingRequiredPlugins(self):
        self.loadedPlugins = map(unicode, self.devIface.loadedPlugins())
        requiredFound = KdeConnectRequiredPlugins & set(self.loadedPlugins)
        return True if requiredFound != KdeConnectRequiredPlugins else False

    def share(self, url):
        url = unicode(url)
        if not url.startswith('file://'):
            url = 'file://' + url
        self.shareIface.shareUrl(url)

    def findMyPhone(self):
        self.findMyPhoneIface.ring()

    def pluginsChangedCheck(self):
        if not self.reachable:
            return
        QtCore.QTimer.singleShot(1000, self.pluginsChanged.emit)
        if not self.hasMissingRequiredPlugins():
            self.missingRequiredPlugin.emit(False)
            return
        #signals are asynchronous, and loadedPlugins might result empty while reachable is still true (and it's not), then we wait a while for it
        QtCore.QTimer.singleShot(1000, lambda: self.missingRequiredPlugin.emit(self.hasMissingRequiredPlugins()) if self.reachable else None)

    def notificationPosted(self, id):
        notification = Notification(self, id)
        self.notifications[id] = notification
        self.notificationsChanged.emit()
        self.newNotification.emit(notification)

    def notificationRemoved(self, id):
#        print 'removed'
        try:
            notification = self.notifications.pop(id)
            notification.deleteLater()
            self.notificationsChanged.emit()
        except:
            pass

    def allNotificationsRemoved(self):
        print 'full remove'
        for id, n in self.notifications.items():
            if n.dismissable:
                del self.notifications[id]
        self.notificationsChanged.emit()

    def createNotifications(self):
        for id in self.notificationIface.activeNotifications():
            notification = Notification(self, id)
            self.notifications[id] = notification
            self.newNotification.emit(notification)
        self.notificationsChanged.emit()

#    def dismissNotification(self, notification):
#        del self.notifications[notification.id]
#        notification.delete()
#        self.notificationsChanged.emit()

    @property
    def notifications(self):
#        print self.notificationIface.activeNotifications()
        return self._notifications

    @property
    def charging(self):
        return self._charging

    @charging.setter
    def charging(self, state):
        if state != self._charging:
            self._charging = bool(state)
            self.chargeStateChanged.emit(self._charging)

    def setCharging(self, state):
        self.charging = state

    @property
    def reachable(self):
        return self._reachable

    @reachable.setter
    def reachable(self, state):
        self._reachable = bool(state)
        self.reachableChanged.emit(self._reachable)

    def setReachable(self, state):
        self.reachable = state

    @property
    def battery(self):
#        self.propsIface.Get('org.kde.kdeconnect.device.battery', 'charge')
        return self._battery

    @battery.setter
    def battery(self, value):
        value = int(value)
        if value != self._battery:
            self._battery = int(value)
            self.batteryChanged.emit(self._battery)

    def refreshBattery(self):
        self.battery = self.batteryIface.charge()

    def setBattery(self, value):
        self.battery = value


class CustomIcon(QtCore.QObject):
    def __init__(self, phone, base='{}/kdeconnect-tray-on.svg'.format(iconsPath)):
        QtCore.QObject.__init__(self)
        self.base = QtSvg.QSvgRenderer(base)
        self.phone = phone
        self.icon = QtGui.QIcon()

    def getIcon(self, size):
        size = size.size()
        rect = QtCore.QRectF(0, 0, size.width(), size.height())
        self.pixmap = QtGui.QPixmap(size)
        self.pixmap.fill(QtGui.QColor(255, 255, 255, 0))
        qp = QtGui.QPainter(self.pixmap)
        self.base.render(qp, rect)
        qp.setRenderHints(qp.Antialiasing)
#        green = self.phone.battery * 2.55
#        red = 255 - green
        qp.setPen(QtGui.QPen(QtGui.QColor(*batteryColor(self.phone.battery)), 2))
        qp.drawLine(3, size.height() - 2, 3, size.height() - 1 - (size.height() - 2) * self.phone.battery * .01)
        notiSize = size.height() / 2.5
        if self.phone.notifications:
            qp.setBrush(QtCore.Qt.white)
            qp.setPen(QtCore.Qt.darkGray)
            font = QtGui.QFont()
            font.setPointSizeF(notiSize - 2)
            qp.setFont(font)
            notifLen = len(self.phone.notifications)
            if notifLen < 10:
                notiRect = QtCore.QRectF(size.width() - 1, size.height() - 1, -notiSize, -notiSize)
                qp.drawEllipse(notiRect)
            else:
                notiRect = QtCore.QRectF(size.width() - 1, size.height() - 1, -QtGui.QFontMetrics(font).width('00') - 2, -notiSize)
                qp.drawRect(notiRect)
            qp.setPen(QtCore.Qt.black)
            qp.drawText(notiRect, QtCore.Qt.AlignCenter, str(len(self.phone.notifications)))
        if self.phone.charging:
            qp.setBrush(QtGui.QColor(50, 200, 255))
            qp.setPen(QtGui.QPen(QtCore.Qt.darkGray, .5))
            path = QtGui.QPainterPath()
            path.lineTo(2, 0)
            path.lineTo(2, -1.5)
            path.lineTo(4, -1.5)
            path.lineTo(6, 2)
            path.lineTo(4, 5.5)
            path.lineTo(2, 5.5)
            path.lineTo(2, 4)
            path.lineTo(0, 3.5)
            path.lineTo(0, 3)
            path.lineTo(2, 3)
            path.lineTo(2, .5)
            path.lineTo(0, .5)
            path.closeSubpath()
            qp.translate(2, size.height() - path.boundingRect().height() + 1)
            qp.drawPath(path)
        self.icon.addPixmap(self.pixmap)
        return self.icon


class AlternateTimer(QtCore.QTimer):
    def __init__(self, *args, **kwargs):
        QtCore.QTimer.__init__(self, *args, **kwargs)
        self.defaultInterval = 0
        self.altInterval = None
        self.altIter = 0
        self.altActive = False
        self.altIterLimit = 1
        self.timeout.connect(self.checkInterval)

    def checkInterval(self):
        if self.interval() == self.altInterval:
            return
        if self.altActive:
            self.altIter += 1
            if self.altIter >= self.altIterLimit:
                self.altActive = False
                QtCore.QTimer.setInterval(self, self.defaultInterval)

    def stop(self):
        QtCore.QTimer.stop(self)
        if self.altActive:
            self.altActive = False
            QtCore.QTimer.setInterval(self, self.defaultInterval)

    def setInterval(self, interval):
        QtCore.QTimer.setInterval(self, interval)
        self.defaultInterval = interval

    def setAltInterval(self, interval, iterLimit=1):
        self.altInterval = interval
        self.altIterLimit = iterLimit
        if self.isActive():
            QtCore.QTimer.setInterval(self, interval)

    def startAlt(self):
        QtCore.QTimer.setInterval(self, self.altInterval if self.altInterval is not None else self.defaultInterval)
        self.altActive = True
        self.start()


class DualTimer(QtCore.QObject):
    timeout0 = QtCore.pyqtSignal()
    timeout1 = QtCore.pyqtSignal()
    timeout = QtCore.pyqtSignal()
    timeoutDual = QtCore.pyqtSignal(int)
    def __init__(self, parent=None):
        QtCore.QObject.__init__(self, parent)
        self.timer0 = QtCore.QTimer()
        self.timer1 = QtCore.QTimer()

        self.timer0.setSingleShot(True)
        self.timer0.timeout.connect(self.timer1.start)
        self.timer0.timeout.connect(self.timeout0)
        self.timer0.timeout.connect(self.timeout)
        self.timer0.timeout.connect(lambda: self.timeoutDual.emit(0))
        self.timer1.setSingleShot(True)
        self.timer1.timeout.connect(self.timer0.start)
        self.timer1.timeout.connect(self.timeout1)
        self.timer1.timeout.connect(self.timeout)
        self.timer1.timeout.connect(lambda: self.timeoutDual.emit(1))
        self._timers = self.timer0, self.timer1
        self.current = 0
        self.currentTimer = self.timer0

    def setInterval0(self, interval):
        self.timer1.setInterval(interval)

    def setInterval1(self, interval):
        self.timer0.setInterval(interval)

    def setInterval(self, interval):
        self.setIntervals(interval, interval)

    def setIntervals(self, i0, i1):
        self.setInterval0(i0)
        self.setInterval1(i1)

    def start(self, id=0):
        self.timer0.stop()
        self.timer1.stop()
        self.current = id
        self.currentTimer = self._timers[id]
        self.currentTimer.start()

    def stop(self):
        self.timer0.stop()
        self.timer1.stop()

    def reset(self):
        self.stop()
        self.current = 0
        self.currentTimer = self._timers[0]

    def isActive(self):
        return any(t.isActive() for t in self._timers)


