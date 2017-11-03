#!/usr/bin/env python2.7
# *-* coding: utf-8 *-*

import sys
import re
import dbus
import pickle
import os
from Queue import PriorityQueue
from threading import Lock
from glob import glob
from PyQt4 import QtGui, QtCore, QtSvg, uic
from dbus.mainloop.qt import DBusQtMainLoop
from collections import namedtuple

MAJ_VERSION = 0
MIN_VERSION = 8
REV_VERSION = 1
VERSION = '{}.{}.{}'.format(MAJ_VERSION, MIN_VERSION, REV_VERSION)

HIGH, LOW = 0, 1
UNREACHABLE, REACHABLE = 0, 1
_iconOn = 'file://' + os.path.join(os.path.dirname(__file__), 'kdeconnect-tray-on.svg')
_iconOff = 'file://' + os.path.join(os.path.dirname(__file__), 'kdeconnect-tray-off.svg')
_icons = _iconOff, _iconOn

urlRegex = re.compile(r'((?:http(?:s)?:\/\/|ftp:\/\/)?[\d\w\@]+\.(?:[\w]{2,5})(?:(?:[\/]*(?![\,\.\:\;]\s)[\S])*)*)+')

NotificationData = namedtuple('NotificationData', 'time app ticker id')
PluginsData = namedtuple('PluginsData', 'text required')
PluginsData.__new__.__defaults__ = (False, )
StatusData = namedtuple('StatusData', 'time reachable battery charging')
SettingsWidgetData = namedtuple('SettingsWidgetData', 'type default children')
SettingsWidgetData.__new__.__defaults__ = (True, )
WidgetNameData = namedtuple('WidgetNameData', 'label data')
#StatusData.__new__.defaults__ = (None, )

IconDisplayRole = QtCore.Qt.UserRole + 1
IconNameRole = IconDisplayRole + 1
EditedIconRole = IconNameRole + 1
DefaultIconRole = EditedIconRole + 1
TimeRole = IconNameRole + 1
PluginRole = TimeRole + 1

SettingsAppTableApp, SettingsAppTableIcon = 0, 1

OFF, ON = 0, 1
STARTDATE, ENDDATE = 0, 1
ALL, DAYS, ENTRIES = 0, 1, 2
ID = '334e5229e64dad3c'

CHECKBOX, SPINBOX, RADIO, LINEEDIT, GROUP = xrange(5)

KdeConnectPlugins = {
    'kdeconnect_pausemusic': PluginsData('Pause media on phone call'), 
    'kdeconnect_findmyphone': PluginsData('Find my phone'), 
    'kdeconnect_share': PluginsData('Share files, links and text'), 
    'kdeconnect_mpriscontrol': PluginsData('Media player control'), 
    'kdeconnect_ping': PluginsData('Ping the device'), 
    'kdeconnect_telephony': PluginsData('Phone call and messages'), 
    'kdeconnect_notifications': PluginsData('Notifications', True), 
    'kdeconnect_mousepad': PluginsData('Trackpad-like and keyboard control'), 
    'kdeconnect_sftp': PluginsData('File system browse'), 
    'kdeconnect_clipboard': PluginsData('Share clipboard content'), 
    'kdeconnect_sendnotifications': PluginsData('Show desktop notifications on the device'), 
    'kdeconnect_screensaver_inhibit': PluginsData('Disable screensaver'), 
    'kdeconnect_runcommand': PluginsData('Run commands'), 
    'kdeconnect_battery': PluginsData('Battery status', True), 
    }

KdeConnectRequiredPlugins = set(p for p, d in KdeConnectPlugins.items() if d.required)

settingsWidgets = {
#    General settings
    'desktopNotifications': SettingsWidgetData(CHECKBOX, True), 
    'lowBatteryIconBlink': SettingsWidgetData(CHECKBOX, True), 
    'lowBatteryIconBlinkValue': SettingsWidgetData(SPINBOX, 10), 

    'notifyReachable': SettingsWidgetData(CHECKBOX, True), 
    'notifyUnreachable': SettingsWidgetData(CHECKBOX, True), 
    'notifyChargeChanged': SettingsWidgetData(CHECKBOX, True), 
    'notifyCharged': SettingsWidgetData(CHECKBOX, True), 
    'notifyBatteryChargeAlert': SettingsWidgetData(CHECKBOX, True), 
    'notifyBatteryChargeAlertIntervals': SettingsWidgetData(LINEEDIT, '50,75,90,95'), 
    'notifyBatteryDischargeAlert': SettingsWidgetData(CHECKBOX, True), 
    'notifyBatteryDischargeAlertIntervals': SettingsWidgetData(LINEEDIT, '20,15,10,5'), 

#    Device notifications settings
    'showUndismissable': SettingsWidgetData(CHECKBOX, True), 
    'keepNotifications': SettingsWidgetData(CHECKBOX, True), 
    'keepNotificationsMode': SettingsWidgetData(GROUP, ALL, (WidgetNameData('All', RADIO), WidgetNameData('Days', RADIO), WidgetNameData('Entries', RADIO))), 
    'keepNotificationsDays': SettingsWidgetData(SPINBOX, 7), 
    'keepNotificationsEntries': SettingsWidgetData(SPINBOX, 200), 
    'keepStatus': SettingsWidgetData(CHECKBOX, True), 
    'keepStatusMode': SettingsWidgetData(GROUP, ALL, (WidgetNameData('All', RADIO), WidgetNameData('Days', RADIO), WidgetNameData('Entries', RADIO))), 
    'keepStatusDays': SettingsWidgetData(SPINBOX, 30), 
    'keepStatusEntries': SettingsWidgetData(SPINBOX, 1000), 
    }

widgetNameSignals = {
    CHECKBOX: WidgetNameData('Chk', 'toggled'), 
    SPINBOX: WidgetNameData('Spin', 'valueChanged'), 
    RADIO: WidgetNameData('Radio', 'toggled'), 
    LINEEDIT: WidgetNameData('Edit', 'textChanged'), 
    }

widgetGetters = {
    CHECKBOX: 'isChecked', 
    RADIO: 'isChecked', 
    SPINBOX: 'value', 
    LINEEDIT: 'text', 
    }

widgetSetters = {
    CHECKBOX: 'setChecked', 
    RADIO: 'setChecked', 
    SPINBOX: 'setValue', 
    LINEEDIT: 'setText', 
    }

def showCenter(widget):
    cursor = QtGui.QCursor().pos()
    desktop = QtGui.QApplication.desktop()
    for d in xrange(desktop.screenCount()):
        currentGeo = desktop.screenGeometry(d)
        if cursor in currentGeo:
            break
    widget.show()
    widget.move(currentGeo.x() + currentGeo.width() / 2 - widget.width() / 2, 
        currentGeo.y() + currentGeo.height() / 2 - widget.height() / 2)


def simpleTimeFormat(time):
    if time <= 60:
        return '{}s'.format(time)
    m, s = divmod(time, 60)
    if time <= 3600:
        return '{}m {:02}s'.format(m, s)
    h, m = divmod(m, 60)
    if time <= 86400:
        return '{}h {:02}m {:02}s'.format(h, m, s)
    d, h = divmod(h, 24)
    return '{}d {:02}h {:02}m {:02}s'.format(d, h, m, s)

def batteryColor(battery):
    if battery < 0:
        battery = 0
    green = battery * 2.55
    red = 255 - green
    return red, green, 0

def emptyIcon(size=12):
    icon = QtGui.QPixmap(size, size)
    insize = size - 1
    icon.fill(QtCore.Qt.transparent)
    qp = QtGui.QPainter(icon)
    qp.setRenderHints(qp.Antialiasing)
    qp.translate(.5, .5)
    qp.setPen(QtCore.Qt.lightGray)
    qp.drawRect(0, 0, insize, insize)
    qp.drawLine(1, 0, insize, insize)
    qp.drawLine(0, insize, insize, 0)
    qp.end()
    return icon

def setBold(item, bold=True):
    if not bold:
        bold = False
    font = item.font()
    font.setBold(bold)
    item.setFont(font)

def setItalic(item, italic=True):
    if not italic:
        italic = False
    font = item.font()
    font.setItalic(italic)
    item.setFont(font)

def getDataDir():
    dataDir = QtGui.QDesktopServices.storageLocation(QtGui.QDesktopServices.DataLocation)
    if not QtCore.QDir(dataDir).exists():
        try:
            QtCore.QDir().mkpath(dataDir + '/icons')
            return False
        except:
            return None
    else:
        try:
            QtCore.QDir().mkpath(dataDir + '/icons')
            return dataDir
        except:
            return None
        return dataDir

def saveIcon(iconName, appName):
    dataDir = getDataDir()
    if dataDir is None:
        return
    pm = QtGui.QPixmap(iconName).scaled(QtCore.QSize(12, 12), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
    try:
        dest = QtCore.QFile('{}/icons/{}.png'.format(dataDir, appName))
        if dest.exists():
            dest.remove()
        return pm.save(dest.fileName())
    except Exception as e:
        print 'Icon save error! {}'.format(e)
        return False


class CheckBoxDelegate(QtGui.QStyledItemDelegate):
    square_pen_enabled = QtGui.QColor(QtCore.Qt.darkGray)
    square_pen_disabled = QtGui.QColor(QtCore.Qt.lightGray)
    square_pen = square_pen_enabled
    select_pen_enabled = QtGui.QColor(QtCore.Qt.black)
    select_pen_disabled = QtGui.QColor(QtCore.Qt.darkGray)
    select_pen = select_pen_enabled
    select_brush_enabled = QtGui.QColor(QtCore.Qt.black)
    select_brush_disabled = QtGui.QColor(QtCore.Qt.black)
    select_brush = select_brush_enabled
    path = QtGui.QPainterPath()
    path.moveTo(2, 5)
    path.lineTo(4, 8)
    path.lineTo(8, 2)
    path.lineTo(4, 6)
    def __init__(self, *args, **kwargs):
        QtGui.QStyledItemDelegate.__init__(self, *args, **kwargs)
        self.square = QtCore.QRectF()

    def paint(self, painter, style, index):
        QtGui.QStyledItemDelegate.paint(self, painter, style, QtCore.QModelIndex())
        if index.flags() & QtCore.Qt.ItemIsEnabled:
            self.square_pen = self.square_pen_enabled
            self.select_pen = self.select_pen_enabled
            self.select_brush = self.select_brush_enabled
        else:
            self.square_pen = self.square_pen_disabled
            self.select_pen = self.select_pen_disabled
            self.select_brush = self.select_brush_disabled
        option = QtGui.QStyleOptionViewItem()
        option.__init__(style)
        self.initStyleOption(option, index)
        painter.setRenderHints(QtGui.QPainter.Antialiasing)
        painter.save()
        painter.translate(option.rect.x() + option.rect.width() / 2 - 5, option.rect.y() + option.rect.height() / 2 - 5)
        painter.setPen(self.square_pen)
        painter.drawRect(0, 0, 10, 10)
        if index.data(QtCore.Qt.CheckStateRole).toBool():
            painter.setPen(self.select_pen)
            painter.setBrush(self.select_brush)
            painter.translate(self.square.left(), self.square.top())
            painter.drawPath(self.path)
        painter.restore()


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
        self.reachable = self.propsIface.Get('org.kde.kdeconnect.device', 'isReachable')

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

        self.name = self.propsIface.Get('org.kde.kdeconnect.device', 'name')
        self.battery = self.batteryIface.charge()
        self.charging = self.batteryIface.isCharging()
        self.createNotifications()


    def hasMissingRequiredPlugins(self):
        self.loadedPlugins = map(unicode, self.devIface.loadedPlugins())
        requiredFound = KdeConnectRequiredPlugins & set(self.loadedPlugins)
        return True if requiredFound != KdeConnectRequiredPlugins else False

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


class BatteryWidget(QtGui.QWidget):
    def __init__(self, phone):
        QtGui.QWidget.__init__(self)
        self.phone = phone
        self.phone.batteryChanged.connect(lambda *args: self.repaint())
        self.phone.chargeStateChanged.connect(lambda *args: self.repaint())
        self.setMaximumSize(9, 16)
        self.setMinimumSize(9, 16)
        self.blinkTimer = QtCore.QTimer()
        self.blinkTimer.setSingleShot(True)
        self.blinkTimer.setInterval(250)
        self.blinkTimer.timeout.connect(self.blink)
        self.blinkTimer.timeout.connect(self.update)
        self.blinkState = True
        self.batteryPen = (QtCore.Qt.NoPen, QtCore.Qt.white)
        self.batteryAlert = self.phone.batteryAlert

    def blink(self):
        self.blinkState = not self.blinkState

    def paintEvent(self, event):
        battery = self.phone.battery
        if battery < self.batteryAlert and not self.phone.charging:
            if not self.blinkTimer.isActive():
                self.blinkTimer.start()
        else:
            self.blinkState = True
        qp = QtGui.QPainter()
        qp.begin(self)
        qp.setRenderHints(qp.Antialiasing)
        qp.translate(.5, .5)
        
        if battery < 100:
            qp.save()
            qp.setPen(QtCore.Qt.NoPen)
            qp.setBrush(QtGui.QColor(*batteryColor(battery)) if self.blinkState else QtCore.Qt.transparent)
            rect = QtCore.QRectF(0, 0, 8, .13 * battery)
            qp.translate(0, 15 - rect.height())
            qp.drawRect(rect)
            qp.restore()
            qp.setBrush(QtCore.Qt.NoBrush)
        else:
            qp.setBrush(QtCore.Qt.green)

        qp.setPen(QtCore.Qt.white if battery > self.batteryAlert else self.batteryPen[self.blinkState])
        path = QtGui.QPainterPath()
        path.moveTo(0, 2)
        path.lineTo(2, 2)
        path.lineTo(2, 0)
        path.lineTo(6, 0)
        path.lineTo(6, 2)
        path.lineTo(8, 2)
        path.lineTo(8, 15)
        path.lineTo(0, 15)
        path.closeSubpath()
        qp.drawPath(path)

        if self.phone.charging:
            qp.setPen(QtGui.QPen(QtCore.Qt.white, .5))
            qp.setBrush(QtGui.QColor(50, 200, 255))
            path = QtGui.QPainterPath()
            path.lineTo(2, 0)
            path.lineTo(2, -2)
            path.lineTo(6, 0)
            path.lineTo(4, 0)
            path.lineTo(4, 2)
            path.closeSubpath()
            qp.translate(1, 7)
            qp.drawPath(path)

        qp.end()

class CustomIcon(QtCore.QObject):
    def __init__(self, phone, base='kdeconnect-tray-on.svg'):
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


class NotificationLabel(QtGui.QTextEdit):
    hideNotification = QtCore.pyqtSignal(object)
    hideAllNotifications = QtCore.pyqtSignal()
    def __init__(self, main, notification):
        QtGui.QTextEdit.__init__(self)
        self.main = main
        self.settings = self.main.settings
#        self.settings.changed.connect(self.iconsChanged)
        self.notification = notification
        self.app = notification.app
        self.setLabel()

        self.setSizePolicy(QtGui.QSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed))
        self.setStyleSheet('QTextEdit {background-color: transparent; color: #ddd;}')
        self.setFrameShape(self.NoFrame)
        self.setFrameShadow(self.Plain)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setCursorWidth(0)
        self.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
#        self.setCursor(QtCore.Qt.ArrowCursor)
        self.viewport().setCursor(QtCore.Qt.ArrowCursor)
        self.menu = QtGui.QMenu()
        self.copySelAction = QtGui.QAction('Copy selected text', self)
        self.copyAction = QtGui.QAction('Copy text', self)
        self.copyNotificationAction = QtGui.QAction('Copy notification info', self)
        self.urlSeparator = QtGui.QAction(self)
        self.urlSeparator.setSeparator(True)
        self.openUrlAction = QtGui.QAction('Open link', self)
        self.copyUrlAction = QtGui.QAction('Copy link location', self)
        sep = QtGui.QAction(self)
        sep.setSeparator(True)
        self.hideAction = QtGui.QAction('Hide notification', self)
        self.hideAction.setEnabled(True if self.notification.dismissable else False)
        self.hideAllAction = QtGui.QAction('Hide all notifications', self)
        self.menu.addActions([self.copySelAction, self.copyAction, self.copyNotificationAction, self.urlSeparator, self.openUrlAction, self.copyUrlAction, sep, self.hideAction, self.hideAllAction])
        self.setMaximumHeight(1)
        self.setMouseTracking(True)
        self.setStyleSheet('border: 1px solid transparent; border-radius: 2px; background: transparent; color: white;')
        self.hoverBorderAnimation = QtCore.QPropertyAnimation(self, 'color')
        self.hoverBorderAnimation.setDuration(150)
        self.hoverBorderAnimation.setStartValue(QtGui.QColor(0, 0, 0, 0))
        self.hoverBorderAnimation.setEndValue(QtGui.QColor(50, 50, 50, 255))

    @QtCore.pyqtProperty(QtGui.QColor)
    def color(self):
        return QtGui.QColor()

    @color.setter
    def color(self, color):
        r, g, b, a = color.getRgb()
        self.setStyleSheet('border: 1px solid rgba({r},{g},{b},{a}); border-radius: 2px; background: rgba(25,25,25,{a}); color: white;'.format(r=r, g=g, b=b, a=a))

    def setLabel(self):
        self.setText(u'{icon}<b>{app}</b><br/>{ticker}'.format(
                icon=self.getAppIcon(), 
                app=self.app, 
                ticker=re.sub(urlRegex, lambda m: u''.join(u'<a href="{t}">{t}</a>'.format(t=t) for t in m.groups()), self.notification.ticker), 
                ))

#    Method disabled until I find a way to reload the image resource
#    def iconsChanged(self, group, key):
#        if group and group == 'customIcons' and key == self.app:
#            self.setLabel()

    def mouseMoveEvent(self, event):
        QtGui.QTextEdit.mouseMoveEvent(self, event)
        if self.document().documentLayout().anchorAt(event.pos()):
            self.viewport().setCursor(QtCore.Qt.PointingHandCursor)
        else:
            self.viewport().setCursor(QtCore.Qt.ArrowCursor)

    def leaveEvent(self, event):
        self.hoverBorderAnimation.setDirection(self.hoverBorderAnimation.Backward)
        self.hoverBorderAnimation.start()
        self.viewport().setCursor(QtCore.Qt.ArrowCursor)

    def enterEvent(self, event):
        self.hoverBorderAnimation.setDirection(self.hoverBorderAnimation.Forward)
        self.hoverBorderAnimation.start()
        self.viewport().setCursor(QtCore.Qt.ArrowCursor)

    def showEvent(self, event):
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)
        self.textCursor().clearSelection()
        self.setFixedSize(self.document().size().toSize())
        QtGui.QTextEdit.show(self)

    def contextMenuEvent(self, event):
        sel = self.textCursor().selection().toPlainText()
        self.copySelAction.setVisible(True if sel else False)
        link = self.document().documentLayout().anchorAt(event.pos())
        if link:
            self.urlSeparator.setVisible(True)
            self.openUrlAction.setVisible(True)
            self.copyUrlAction.setVisible(True)
        else:
            self.urlSeparator.setVisible(False)
            self.openUrlAction.setVisible(False)
            self.copyUrlAction.setVisible(False)
        res = self.menu.exec_(self.viewport().mapToGlobal(event.pos()))
        if res == self.copySelAction:
            QtGui.QApplication.clipboard().setText(sel)
        elif res == self.copyAction:
            QtGui.QApplication.clipboard().setText(self.notification.ticker)
        elif res == self.copyNotificationAction:
            QtGui.QApplication.clipboard().setText(
                u'{app} ({date}): {ticker}'.format(
                    app=self.app, 
                    date=QtCore.QDateTime.fromMSecsSinceEpoch(self.notification.time * 1000).toString('dd/MM/yy hh:mm:ss'), 
                    ticker=self.notification.ticker
                    )
                )
        elif res == self.copyUrlAction:
            linkCheck = unicode(link).lower()
            if not linkCheck.startswith('http://') and not linkCheck.startswith('https://') and not linkCheck.startswith('ftp://'):
                link = u'http://{}'.format(link)
            QtGui.QApplication.clipboard().setText(link)
        elif res == self.openUrlAction:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(link))
        elif res == self.hideAction:
            self.hideNotification.emit(self.notification)
        elif res == self.hideAllAction:
            self.hideAllNotifications.emit()

    def getAppIcon(self):
        self.settings.beginGroup('customIcons')
        iconName = self.settings.value(self.app).toString()
        self.settings.endGroup()
        if iconName == 'false':
            return '&nbsp;'
        elif iconName and iconName != 'true':
            return u'<img src="{}/{}.png"> '.format(self.main.iconsPath, self.app)
        elif self.app in self.main.defaultIcons:
            return u'<img src="icons/{}.png"> '.format(self.app)
        else:
            return '&nbsp;'

class ToolTipWidget(QtGui.QWidget):
    def __init__(self, main, phone):
        QtGui.QWidget.__init__(self, None, QtCore.Qt.ToolTip)
        self.main = main
        self.settings = self.main.settings
        self.phone = phone
        palette = self.palette()
        palette.setColor(QtGui.QPalette.Background, QtGui.QColor(20, 20, 20))
        palette.setColor(QtGui.QPalette.Foreground, QtCore.Qt.white)
        self.setPalette(palette)
        layout = QtGui.QGridLayout()
        layout.setVerticalSpacing(2)
        layout.setContentsMargins(4, 4, 4, 4)
        self.setLayout(layout)
        header = QtGui.QHBoxLayout()
        header.setSpacing(4)
        layout.addLayout(header, 0, 0)
        self.nameLabel = QtGui.QLabel()
        header.addWidget(self.nameLabel)
        icon = BatteryWidget(self.phone)
        header.addWidget(icon)
        self.batteryLabel = QtGui.QLabel()
        header.addWidget(self.batteryLabel)
        hspacer = QtGui.QWidget()
        hspacer.setSizePolicy(QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Maximum))
        header.addWidget(hspacer)
        self.spacer = QtGui.QFrame()
        self.spacer.setFrameShape(self.spacer.HLine)
        self.spacer.setFrameShadow(self.spacer.Sunken)
        layout.addWidget(self.spacer)
        self.notificationLayout = QtGui.QGridLayout()
        layout.addLayout(self.notificationLayout, layout.rowCount(), 0)

        self.phone.batteryChanged.connect(self.updatePhone)
        self.phone.chargeStateChanged.connect(self.updatePhone)
        self.phone.notificationsChanged.connect(self.updatePhone)
        self.notifications = {}
        self.setMinimumWidth(150)
        self.mouseTimer = AlternateTimer()
        self.mouseTimer.setInterval(200)
        self.mouseTimer.setAltInterval(500)
        self.mouseTimer.timeout.connect(self.leaveCheck)
        self.iconRect = QtCore.QRect()
        self.appIcons = {}
        self.estimated = ''

    def updatePhone(self, *args):
        self.nameLabel.setText('<big><b>{}</b></big>'.format(self.phone.name))
        if self.phone.charging:
            if self.phone.battery == 100:
                charging = ' (charged!)'
            else:
                charging = ' (charging{}'.format(self.estimated)
        else:
            charging = self.estimated
        self.batteryLabel.setText('<font color="#{color}">{battery}%</font>{charging}'.format(
            color='{:02x}{:02x}{:02x}'.format(*map(int, batteryColor(self.phone.battery))), 
            battery=self.phone.battery, 
#            charging=' (charging{})'.format(self.estimated) if self.phone.charging else self.estimated
            charging=charging
            ))
        self.spacer.setVisible(True if self.phone.notifications else False)
        delete = set()
        dismissable = []
        normal = []
        showUndismissable = self.settings.value('showUndismissable')
        for id in sorted(self.phone.notifications.keys()):
            n = self.phone.notifications[id]
            if not n.dismissable:
                if not showUndismissable:
                    delete.add(n)
                else:
                    dismissable.append(n)
            else:
                normal.append(n)
        for n in dismissable + normal:
            if n in self.notifications:
                continue
            label = NotificationLabel(self.main, n)
            btn = QtGui.QPushButton()
            if n.dismissable:
                label.hideNotification.connect(self.dismissNotification)
                label.hideAllNotifications.connect(lambda: [self.dismissNotification(n) for n in self.notifications.keys()])
                btn.setIcon(self.style().standardIcon(QtGui.QStyle.SP_DialogCloseButton))
                btn.setMaximumSize(22, 22)
                btn.clicked.connect(lambda state, n=n: self.dismissNotification(n))
                self.notificationLayout.addWidget(label)
                self.notificationLayout.addWidget(btn, self.notificationLayout.rowCount() - 1, 1)
            else:
                self.notificationLayout.addWidget(label, self.notificationLayout.rowCount(), 0, 1, 2)
            self.notifications[n] = label, btn
#            print self.sizeHint()
        self.adjustSize()
        for n in self.notifications:
            if not n in self.phone.notifications.values():
                delete.add(n)
        if not delete:
            return
        for n in delete:
            label, btn = self.notifications.pop(n)
            self.notificationLayout.removeWidget(label)
            try:
                self.notificationLayout.removeWidget(btn)
            except:
                pass
            label.deleteLater()
            btn.deleteLater()
            n.deleteLater()
        self.dynResize()

    def dismissNotification(self, notification):
        notification.dismiss()
        label, btn = self.notifications.pop(notification)
        try:
            del self.phone.notifications[notification.id]
        except:
            pass
        if not self.notifications:
            self.spacer.setVisible(False)
#        self.phone.dismissNotification(notification)
        self.notificationLayout.removeWidget(label)
        try:
            self.notificationLayout.removeWidget(btn)
        except:
            pass
        label.deleteLater()
        btn.deleteLater()
        self.dynResize()
        self.updatePhone()

    def dynResize(self):
        if self.iconRect.y() < 100:
            #sopra
            self.adjustSize()
            return
        #sotto
        self.setGeometry(self.x(), self.y() + self.height() - self.sizeHint().height(), self.width(), self.sizeHint().height())
        self.mouseTimer.startAlt()

    def leaveEvent(self, event):
        if not self.mouseTimer.altActive:
            self.mouseTimer.stop()
            QtCore.QTimer.singleShot(200, self.leave)

    def leave(self):
        pos = QtGui.QCursor.pos()
        if not pos in self.geometry() and not pos in self.iconRect:
            self.hide()
        else:
            self.mouseTimer.start()

    def leaveCheck(self):
        pos = QtGui.QCursor.pos()
        if pos in self.geometry():
            self.mouseTimer.stop()
        elif pos not in self.iconRect:
            self.hide()
            self.mouseTimer.stop()

    def setSysTrayIconGeometry(self, geo):
        self.iconRect = geo

    def showEvent(self, *event):
        desktop = QtGui.QApplication.desktop()
        x = self.iconRect.x()
        y = self.iconRect.y()
        if x + self.width() > desktop.width():
            x = desktop.width() - self.width() - 4
        elif x < 0:
            x = 0
        if y > 10:
            y = self.iconRect.y() - self.height() - 4
        else:
            y += self.iconRect.height()
        self.move(x, y)
        self.mouseTimer.start()

    def resizeEvent(self, event):
        self.showEvent()
        bmp = QtGui.QBitmap(event.size())
        bmp.clear()
        qp = QtGui.QPainter(bmp)
#        qp.setRenderHints(qp.Antialiasing)
        qp.setPen(QtCore.Qt.NoPen)
        qp.setBrush(QtCore.Qt.black)
        qp.drawRoundedRect(0, 0, event.size().width(), event.size().height(), 4., 4.)
        qp.end()
        self.setMask(bmp)


class SettingsDialog(QtGui.QDialog):
    keepNotificationsChanged = QtCore.pyqtSignal(int, int)
    keepStatusChanged = QtCore.pyqtSignal(int, int)
    changedSignals = (
        'keepNotifications', 
        'keepStatus', 
        )

    def __init__(self, main):
        QtGui.QDialog.__init__(self)
        uic.loadUi('settings.ui', self)
        self.main = main
        self.settings = QtCore.QSettings()
        self.changeDeviceBtn.clicked.connect(self.changeDevice)

        self.notifyBatteryDischargeAlertIntervalsEdit.setValidator(LowBatteryAlertValidator())
        self.notifyBatteryDischargeAlertIntervalsEdit.focusOutEvent = self.batteryAlertCheck
        self.notifyBatteryDischargeAlertResetBtn.setIcon(QtGui.QIcon.fromTheme('edit-undo'))
        self.notifyBatteryDischargeAlertResetBtn.clicked.connect(lambda: self.notifyBatteryDischargeAlertIntervalsEdit.setText('20,15,10,5'))

        self.notifyBatteryChargeAlertIntervalsEdit.setValidator(HighBatteryAlertValidator())
        self.notifyBatteryChargeAlertIntervalsEdit.focusOutEvent = self.batteryChargeCheck
        self.notifyBatteryChargeResetBtn.setIcon(QtGui.QIcon.fromTheme('edit-undo'))
        self.notifyBatteryChargeResetBtn.clicked.connect(lambda: self.notifyBatteryChargeAlertIntervalsEdit.setText('50,75,90,95'))

        self.widgetSignals = []
        for item, data in settingsWidgets.items():
            if data.type == GROUP:
                for child in data.children:
                    widget = getattr(self, '{name}{child}{type}'.format(name=item, child=child.label, type=widgetNameSignals[child.data].label))
                    signal = getattr(widget, widgetNameSignals[child.data].data)
                    signal.connect(lambda: self.buttonBox.button(self.buttonBox.Apply).setEnabled(True))
                    self.widgetSignals.append(widget)
                continue
            widget = getattr(self, '{name}{type}'.format(name=item, type=widgetNameSignals[data.type].label))
            signal = getattr(widget, widgetNameSignals[data.type].data)
            signal.connect(lambda: self.buttonBox.button(self.buttonBox.Apply).setEnabled(True))
            self.widgetSignals.append(widget)

        self.appModel = QtGui.QStandardItemModel()
        self.appTable.setModel(self.appModel)
        self.appModel.dataChanged.connect(self.appModelCheck)
        self.appTable.customContextMenuRequested.connect(self.appMenu)
        self.appTable.doubleClicked.connect(self.appDoubleClick)
#        self.appTable.doubleClicked.connect(self.enableDelAppBtn)
#        self.appTable.clicked.connect(self.enableDelAppBtn)
#        self.appTable.activated.connect(self.enableDelAppBtn)
        self.appTable.selectionModel().selectionChanged.connect(self.enableDelAppBtn)
        self.addAppBtn.setIcon(QtGui.QIcon.fromTheme('document-new'))
        self.delAppBtn.setIcon(QtGui.QIcon.fromTheme('edit-delete'))

        self.keepNotificationsModeGroup.setId(self.keepNotificationsModeAllRadio, ALL)
        self.keepNotificationsModeGroup.setId(self.keepNotificationsModeDaysRadio, DAYS)
        self.keepNotificationsModeGroup.setId(self.keepNotificationsModeEntriesRadio, ENTRIES)
        self.keepStatusModeGroup.setId(self.keepStatusModeAllRadio, ALL)
        self.keepStatusModeGroup.setId(self.keepStatusModeDaysRadio, DAYS)
        self.keepStatusModeGroup.setId(self.keepStatusModeEntriesRadio, ENTRIES)
        self.keepNotificationsChk.toggled.connect(self.keepNotificationsEnable)
        self.keepStatusChk.toggled.connect(self.keepStatusEnable)
        self.buttonBox.button(self.buttonBox.Apply).clicked.connect(self.setSettings)
        self.clearNotificationsBtn.clicked.connect(self.clearNotificationsCache)
        self.clearStatusBtn.clicked.connect(self.clearStatusCache)

        self.keepNotificationsDaysSpin.valueChanged.connect(
            lambda d, lbl=self.keepNotificationsDaysLbl: self.setStatisticsLabel(d, lbl))
        self.keepStatusDaysSpin.valueChanged.connect(
            lambda d, lbl=self.keepStatusDaysLbl: self.setStatisticsLabel(d, lbl))

    def changeDevice(self):
        deviceDialog = DeviceDialog(self.main.phone.id, self, alert=True)
        newID = deviceDialog.exec_()
        if not newID:
            return
#        newID = deviceDialog.deviceTable.currentIndex().sibling(deviceDialog.deviceTable.currentIndex().row(), 0).data().toPyObject()
        if self.main.phone.id != newID:
            #restart?
            QtGui.QApplication.quit()
            pass

    def setStatisticsLabel(self, days, label):
        if days <= 30:
            label.setText('days')
        else:
            months, days = divmod(days, 30)
            label.setText('days (~{m} month{mp} {d} day{dp})'.format(
                m=months, 
                d=days, 
                mp='s' if months > 1 else '', 
                dp='s' if days > 1 else '', 
                ))
#        print days, label

    def batteryAlertCheck(self, event):
        if not self.notifyBatteryDischargeAlertIntervalsEdit.text():
            self.notifyBatteryDischargeAlertIntervalsEdit.setText('10')
        else:
            alerts = sorted(set(map(int, unicode(self.notifyBatteryDischargeAlertIntervalsEdit.text()).replace(' ', '').strip(',').split(','))), reverse=True)
            self.notifyBatteryDischargeAlertIntervalsEdit.setText(','.join(map(str, alerts)))
        QtGui.QLineEdit.focusOutEvent(self.notifyBatteryDischargeAlertIntervalsEdit, event)

    def batteryChargeCheck(self, event):
        if not self.notifyBatteryChargeAlertIntervalsEdit.text():
            self.notifyBatteryChargeAlertIntervalsEdit.setText('90')
        else:
            alerts = sorted(set(i for i in map(int, unicode(self.notifyBatteryChargeAlertIntervalsEdit.text()).replace(' ', '').strip(',').split(',')) if i >= 50))
            self.notifyBatteryChargeAlertIntervalsEdit.setText(','.join(map(str, alerts)))
        QtGui.QLineEdit.focusOutEvent(self.notifyBatteryChargeAlertIntervalsEdit, event)

    def appModelCheck(self, start, end):
        self.appModel.blockSignals(True)
        for row in xrange(start.row(), end.row() + 1):
            appItem = self.appModel.item(row, SettingsAppTableApp)
            iconItem = self.appModel.item(row, SettingsAppTableIcon)
            icon = iconItem.data(QtCore.Qt.DecorationRole).toPyObject()
            setBold(appItem, iconItem.data(EditedIconRole).toPyObject())
#            appItem.setData(None if not iconItem.data(DefaultIconRole).toPyObject() else QtGui.QBrush(QtCore.Qt.darkGray), QtCore.Qt.ForegroundRole)
            if icon is not None:
                iconItem.setData(QtGui.QBrush(QtCore.Qt.lightGray), QtCore.Qt.BackgroundRole)
            else:
                iconItem.setData(None, QtCore.Qt.BackgroundRole)
        self.appModel.blockSignals(False)

    def enableDelAppBtn(self, selected, deselected):
        indexes = any(index.sibling(index.row(), 1).data(QtCore.Qt.DecorationRole).toPyObject() is not None for index in self.appTable.selectionModel().selection().indexes())
        self.delAppBtn.setEnabled(indexes)

    def clearNotificationsCache(self):
        res = QtGui.QMessageBox.question(
            self, 
            'Clear all notifications?', 
            'Do you want to clear <b>all</b> notifications currently in cache?', 
            QtGui.QMessageBox.Yes|QtGui.QMessageBox.No
            )
        if res == QtGui.QMessageBox.Yes:
            self.main.clearNotificationsCache()

    def clearStatusCache(self):
        res = QtGui.QMessageBox.question(
            self, 
            'Clear all status data?', 
            'Do you want to clear <b>all</b> device status data currently in cache?', 
            QtGui.QMessageBox.Yes|QtGui.QMessageBox.No
            )
        if res == QtGui.QMessageBox.Yes:
            self.main.clearStatusCache()

    def keepNotificationsEnable(self, state):
        for b in self.keepNotificationsModeGroup.buttons() + [self.keepNotificationsDaysLbl, self.keepNotificationsEntriesLbl]:
            b.setEnabled(state)
        if not state:
            self.keepNotificationsDaysSpin.setEnabled(False)
            self.keepNotificationsEntriesSpin.setEnabled(False)
        else:
            if self.keepNotificationsModeGroup.checkedId() == DAYS:
                self.keepNotificationsDaysSpin.setEnabled(True)
            elif self.keepNotificationsModeGroup.checkedId() == ENTRIES:
                self.keepNotificationsEntriesSpin.setEnabled(True)

    def keepStatusEnable(self, state):
        for b in self.keepStatusModeGroup.buttons() + [self.keepStatusDaysLbl, self.keepStatusEntriesLbl]:
            b.setEnabled(state)
        if not state:
            self.keepStatusDaysSpin.setEnabled(False)
            self.keepStatusEntriesSpin.setEnabled(False)
        else:
            if self.keepStatusModeGroup.checkedId() == DAYS:
                self.keepStatusDaysSpin.setEnabled(True)
            elif self.keepStatusModeGroup.checkedId() == ENTRIES:
                self.keepStatusEntriesSpin.setEnabled(True)

    def exec_(self):
        self.main.historyDialog.hide()
        self.readSettings()
        self.buttonBox.button(self.buttonBox.Apply).setEnabled(False)
        self.appModel.clear()
        self.appModel.setHorizontalHeaderLabels(['App name', 'Icon'])
        self.settings.beginGroup('customIcons')
        self.appList = set()
        for app in sorted(self.settings.childKeys()):
            app = unicode(app)
            self.appList.add(app)
            appItem = QtGui.QStandardItem(app)
            iconItem = QtGui.QStandardItem()
            customValue = unicode(self.settings.value(app).toString())
            if customValue and customValue != 'false':
                if customValue in self.main.defaultIcons:
                    icon = self.main.defaultIcons[customValue]
                else:
                    icon = QtGui.QIcon('{}/{}.png'.format(self.main.iconsPath, app))
                iconItem.setData(icon, QtCore.Qt.DecorationRole)
                iconItem.setData(QtGui.QBrush(QtCore.Qt.lightGray), QtCore.Qt.BackgroundRole)
                iconItem.setData(QtCore.Qt.AlignCenter, QtCore.Qt.TextAlignmentRole)
                iconItem.setData(app, IconNameRole)
#                iconItem.setData(iconName, QtCore.Qt.ToolTipRole)
            self.appModel.appendRow([appItem, iconItem])
        defaults = {}
        unknown = {}
        for n in self.main.notificationsHistory:
            if n.app in self.appList:
                continue
            self.appList.add(n.app)
            appItem = QtGui.QStandardItem(n.app)
            iconItem = QtGui.QStandardItem()
            if n.app in self.main.defaultIcons:
                iconName = '{}.png'.format(n.app)
                iconItem.setData(self.main.defaultIcons[n.app], QtCore.Qt.DecorationRole)
                iconItem.setData(QtGui.QBrush(QtCore.Qt.lightGray), QtCore.Qt.BackgroundRole)
                iconItem.setData(QtCore.Qt.AlignCenter, QtCore.Qt.TextAlignmentRole)
                iconItem.setData(iconName, IconNameRole)
                iconItem.setData(iconName, QtCore.Qt.ToolTipRole)
                appItem.setData(QtGui.QBrush(QtCore.Qt.darkGray), QtCore.Qt.ForegroundRole)
                defaults[appItem] = iconItem
            else:
                appItem.setData(QtGui.QBrush(QtCore.Qt.lightGray), QtCore.Qt.ForegroundRole)
                unknown[appItem] = iconItem
#            self.appModel.appendRow([appItem, iconItem])
        for app in sorted(defaults):
            self.appModel.appendRow([app, defaults[app]])
        for app in sorted(unknown):
            self.appModel.appendRow([app, unknown[app]])
        self.settings.endGroup()
        self.appTable.resizeColumnToContents(1)
        self.appTable.horizontalHeader().setResizeMode(0, QtGui.QHeaderView.Stretch)
        self.appTable.horizontalHeader().setResizeMode(1, QtGui.QHeaderView.Fixed)
        res = QtGui.QDialog.exec_(self)
        if res:
            self.setSettings()
        return res

    
    def setSettings(self):
        for item, data in settingsWidgets.items():
            if data.type == GROUP:
                group = getattr(self, '{}Group'.format(item))
                checkedId = group.checkedId()
                if checkedId != data.default:
                    self.settings.setValue(item, checkedId)
                else:
                    self.settings.remove(item)
                if item in self.changedSignals:
                    print checkedId
                    print data.children
#                    getattr(self, '{}Changed'.format(item)).emit(checkedId, )
                continue
            widget = getattr(self, '{}{}'.format(item, widgetNameSignals[data.type].label))
            value = getattr(widget, widgetGetters[data.type])()
            if value != data.default:
                self.settings.setValue(item, value)
            else:
                self.settings.remove(item)
        self.settings.beginGroup('customIcons')
        for row in xrange(self.appModel.rowCount()):
            app = self.appModel.item(row, SettingsAppTableApp).text()
            iconItem = self.appModel.item(row, SettingsAppTableIcon)
            if not iconItem.data(EditedIconRole).toPyObject():
                continue
            if iconItem.data(DefaultIconRole).toPyObject():
                self.settings.remove(app)
            else:
                iconName = unicode(iconItem.data(IconNameRole).toPyObject())
                #TODO: check for write errors
                if iconName.startswith('/'):
                    if not saveIcon(iconName, unicode(app)):
                        print 'error saving {} to {}'.format(app, iconName)
                        return
                    self.settings.setValue(app, 'true')
                else:
                    dest = QtCore.QFile(u'{}/{}.png'.format(self.main.iconsPath, app))
                    if dest.exists():
                        dest.remove()
                    if not QtCore.QFile.copy('icons/{}'.format(iconName), dest.fileName()):
                        print 'error saving {} to {}'.format(app, iconName)
                        return
                    self.settings.setValue(app, 'true')
#                    pm = QtGui.QPixmap(iconName).scaled(QtCore.QSize(12, 12), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
#                self.settings.setValue(app, iconItem.data(IconNameRole))
        self.settings.endGroup()
        self.settings.sync()
        self.buttonBox.button(self.buttonBox.Apply).setEnabled(False)

    def readSettings(self):
        for w in self.widgetSignals:
                w.blockSignals(True)
        for item, data in settingsWidgets.items():
            if data.type == GROUP:
                getattr(self, '{}Group'.format(item)).button(int(self.settings.value(item, data.default).toPyObject())).setChecked(True)
                continue
            widget = getattr(self, '{name}{type}'.format(name=item, type=widgetNameSignals[data.type].label))
            value = self.settings.value(item, data.default).toPyObject()
            if not isinstance(value, type(data.default)):
                if isinstance(data.default, bool):
                    if value == 'false':
                        value = False
                    else:
                        value = bool(value)
                elif isinstance(data.default, int):
                    value = int(value)
                elif isinstance(data.default, float):
                    value = float(value)
                elif isinstance(data.default, (str, unicode)):
                    value = unicode(value)
            getattr(widget, widgetSetters[data.type])(value)

        self.setStatisticsLabel(self.keepNotificationsDaysSpin.value(), self.keepNotificationsDaysLbl)
        self.setStatisticsLabel(self.keepStatusDaysSpin.value(), self.keepStatusDaysLbl)

        for w in self.widgetSignals:
                w.blockSignals(False)

        devProxy = dbus.SessionBus().get_object('org.kde.kdeconnect', '/modules/kdeconnect/devices/' + self.main.phone.id)
        devIface = dbus.Interface(devProxy, dbus_interface='org.freedesktop.DBus.Properties')
        devType = unicode(devIface.Get('org.kde.kdeconnect.device', 'type'))
        devName = unicode(devIface.Get('org.kde.kdeconnect.device', 'name'))
        self.deviceIconLbl.setPixmap(QtGui.QIcon.fromTheme('computer-laptop' if devType == 'laptop' else devType).pixmap(self.fontMetrics().height()))
        self.deviceNameLbl.setText('<b>{name}</b> ({id})'.format(name=devName, id=self.main.phone.id))

#        try:
#            self.devicePluginsBtn.disconnect()
#        except:
#            pass
        self.devicePluginsBtn.clicked.connect(lambda: PluginsDialog(self, self.main.phone.id, devProxy).exec_())

    def appDoubleClick(self, index):
        appIndex = index.sibling(index.row(), 0)
        app = appIndex.data().toString()
        self.iconEdit(app, appIndex.row())

    def appMenu(self, pos):
        index = self.appTable.indexAt(pos)
        if not index.isValid():
            return
        appIndex = index.sibling(index.row(), 0)
        iconIndex = index.sibling(index.row(), 1)
        iconItem = self.appModel.itemFromIndex(iconIndex)
        app = unicode(appIndex.data().toString())
        menu = QtGui.QMenu(self)
        editItem = QtGui.QAction('Edit "{}"...'.format(app), self)
        resetItem = QtGui.QAction('Reset icon for "{}"'.format(app), self)
        if not app in self.main.defaultIcons:
            resetItem.setEnabled(False)
        clearItem = QtGui.QAction('Clear icon for "{}"'.format(app), self)
        if iconIndex.data(QtCore.Qt.DecorationRole).toPyObject() is None:
            clearItem.setEnabled(False)
        menu.addActions([editItem, resetItem, clearItem])
        res = menu.exec_(self.appTable.viewport().mapToGlobal(pos))
        if not res:
            return
        if res == editItem:
            self.iconEdit(app, appIndex.row())
        elif res == clearItem:
#            self.appModel.itemFromIndex(appIndex).setData(QtGui.QBrush(QtCore.Qt.darkGray), QtCore.Qt.ForegroundRole)
            iconItem.setData(None, QtCore.Qt.DecorationRole)
            iconItem.setData(True, EditedIconRole)
            iconItem.setData(False, DefaultIconRole)
            iconItem.setData('noicon', IconNameRole)
            self.buttonBox.button(self.buttonBox.Apply).setEnabled(True)
        elif res == resetItem:
            iconItem.setData(self.main.defaultIcons[app], QtCore.Qt.DecorationRole)
            iconItem.setData(True, EditedIconRole)
            iconItem.setData(True, DefaultIconRole)
            iconItem.setData('{}.png'.format(app), IconNameRole)
            self.buttonBox.button(self.buttonBox.Apply).setEnabled(True)

    def iconEdit(self, app, row):
        dialog = IconEditDialog(self, app, True, self.appList)
        if not dialog.exec_():
            return
        self.buttonBox.button(self.buttonBox.Apply).setEnabled(True)
        if dialog.appChanged:
            oldApp = app
            app = dialog.appEdit.text()
            self.appModel.item(row, 0).setText(app)
            self.appList.remove(unicode(oldApp))
            self.appList.add(unicode(app))
            self.buttonBox.button(self.buttonBox.Apply).setEnabled(True)
        if dialog.iconChanged:
            self.settings.beginGroup('customIcons')
            iconItem = self.appModel.item(row, SettingsAppTableIcon)
            iconItem.setData(True, EditedIconRole)
            if app in self.settings.childKeys():
                default = dialog.currentItem.data(DefaultIconRole).toPyObject()
                if default:
                    iconItem.setData(dialog.currentItem.data(QtCore.Qt.DecorationRole), QtCore.Qt.DecorationRole)
                    iconItem.setData(True, DefaultIconRole)
                else:
                    iconItem.setData(dialog.currentItem.data(QtCore.Qt.DecorationRole) if dialog.iconName != 'noicon' else None, QtCore.Qt.DecorationRole)
                    iconItem.setData(dialog.iconName if dialog.iconName else 'noicon', IconNameRole)
                self.settings.endGroup()
                return
            if dialog.iconName:
                iconItem.setData(QtGui.QIcon(dialog.iconName), QtCore.Qt.DecorationRole)
                iconItem.setData(dialog.iconName, IconNameRole)
            else:
                iconItem.setData(None, QtCore.Qt.DecorationRole)
                iconItem.setData('noicon', IconNameRole)
            self.settings.endGroup()
            self.buttonBox.button(self.buttonBox.Apply).setEnabled(True)


class PluginsDialog(QtGui.QDialog):
    def __init__(self, parent, deviceID, devProxy):
        QtGui.QDialog.__init__(self, parent)
        layout = QtGui.QGridLayout()
        self.setLayout(layout)

        devProxy = dbus.SessionBus().get_object('org.kde.kdeconnect', '/modules/kdeconnect/devices/' + deviceID)
        propsIface = dbus.Interface(devProxy, dbus_interface='org.freedesktop.DBus.Properties')
        self.devIface = dbus.Interface(devProxy, dbus_interface='org.kde.kdeconnect.device')

        name = propsIface.Get('org.kde.kdeconnect.device', 'name')
        self.setWindowTitle('Device plugins configuration')
        layout.addWidget(QtGui.QLabel(
            'Available plugins for device "{}":'.format(name)))

        self.settings = QtCore.QSettings(self.devIface.pluginsConfigFile(), QtCore.QSettings.NativeFormat)

        self.pluginsTable = QtGui.QTableView()
        layout.addWidget(self.pluginsTable)
        self.pluginsModel = QtGui.QStandardItemModel()
        self.pluginsTable.setModel(self.pluginsModel)
        self.pluginsTable.setItemDelegateForColumn(1, CheckBoxDelegate())
        self.pluginsTable.setSelectionMode(self.pluginsTable.NoSelection)
        self.pluginsTable.setEditTriggers(self.pluginsTable.NoEditTriggers)
        self.pluginsTable.setVerticalScrollMode(self.pluginsTable.ScrollPerPixel)
        self.pluginsTable.horizontalHeader().setVisible(False)
        self.pluginsTable.verticalHeader().setVisible(False)
        availablePlugins = self.devIface.loadedPlugins()
        for plugin in propsIface.Get('org.kde.kdeconnect.device', 'supportedPlugins'):
            plugin = unicode(plugin)
            pluginName, pluginRequired = KdeConnectPlugins[plugin]
            pluginItem = QtGui.QStandardItem(pluginName)
            pluginItem.setEnabled(not pluginRequired)
            pluginItem.setData(plugin, PluginRole)
            editableItem = QtGui.QStandardItem()
            editableItem.setData(2 if plugin in availablePlugins else 0, QtCore.Qt.CheckStateRole)
            editableItem.setCheckable(True)
            editableItem.setEnabled(not pluginRequired)
            self.pluginsModel.appendRow([pluginItem, editableItem])
        self.pluginsTable.resizeColumnsToContents()
        self.pluginsTable.resizeRowsToContents()
        self.pluginsTable.horizontalHeader().setResizeMode(0, QtGui.QHeaderView.Stretch)
        self.pluginsTable.horizontalHeader().setResizeMode(1, QtGui.QHeaderView.Fixed)
        self.buttonBox = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok|QtGui.QDialogButtonBox.Cancel)
        self.buttonBox.button(self.buttonBox.Ok).setEnabled(False)
        self.pluginsModel.dataChanged.connect(lambda *args: self.buttonBox.button(self.buttonBox.Ok).setEnabled(True))
        self.buttonBox.button(self.buttonBox.Ok).clicked.connect(self.setPlugins)
        self.buttonBox.button(self.buttonBox.Cancel).clicked.connect(self.reject)
        layout.addWidget(self.buttonBox)

    def setPlugins(self):
        self.settings.beginGroup('plugins')
        for row in xrange(self.pluginsModel.rowCount()):
            editableItem = self.pluginsModel.item(row, 1)
            if not editableItem.isEnabled():
                continue
            pluginItem = self.pluginsModel.item(row, 0)
            pluginNameFull = '{}Enabled'.format(pluginItem.data(PluginRole).toString())
            pluginState = editableItem.data(QtCore.Qt.CheckStateRole).toBool()
            if pluginState != self.settings.value(pluginNameFull).toBool():
#                print pluginItem.text(), pluginItem.data(PluginRole).toString(), pluginState, self.settings.value(pluginNameFull).toBool()
                self.settings.setValue(pluginNameFull, pluginState)
        self.settings.endGroup()
        self.settings.sync()
        self.devIface.reloadPlugins()
        self.accept()


class IconDelegate(QtGui.QStyledItemDelegate):
    def __init__(self, combo):
        QtGui.QStyledItemDelegate.__init__(self)
        self.combo = combo
        self.textPadding = 20
        self.rightMargin = 2

    def paint(self, painter, style, index):
        option = QtGui.QStyleOptionViewItemV4()
        option.__init__(style)
        self.initStyleOption(option, index)
        iconName = index.data(IconDisplayRole).toPyObject()
        if not iconName:
            iconName = ''
        textWidth = option.fontMetrics.width(iconName)
#        print iconName, self.textPadding, textWidth, self.rightMargin, option.rect.width()
        fullWidth = self.textPadding + textWidth + self.rightMargin
        if fullWidth > option.rect.width():
            scrollBar = self.combo.view().width() - self.combo.view().viewport().width()
            self.combo.view().setMinimumWidth(fullWidth + scrollBar)
        QtGui.QStyledItemDelegate.paint(self, painter, option, index)
        painter.save()
        appStyle = QtGui.QApplication.style()
        painter.translate(self.textPadding if option.state & appStyle.State_Enabled else 0, 0)
        if option.state & appStyle.State_Selected:
            textStyle = option.palette.HighlightedText
        else:
            textStyle = option.palette.Text
        appStyle.drawItemText(painter, option.rect, option.displayAlignment, option.palette, True, iconName, textStyle)
        painter.restore()

class IconEditDialog(QtGui.QDialog):
    def __init__(self, parent, app, editable=False, appList=None):
        QtGui.QDialog.__init__(self, parent)
        self.main = parent.main
        self.app = unicode(app)
        self.setWindowTitle('Select icon for "{}"'.format(self.app))
        self.settings = self.main.settings
        self.appChanged = False
        self.iconChanged = False
        layout = QtGui.QGridLayout()
        self.setLayout(layout)
        if editable:
            label = QtGui.QLabel('Select icon for this app:'.format(self.app))
            layout.addWidget(label, 0, 0, 1, 4)
            self.appEdit = QtGui.QLineEdit(self.app)
            self.appEdit.textChanged.connect(self.appEditChanged)
            self.appList = appList
            layout.addWidget(self.appEdit)
        else:
            label = QtGui.QLabel('Select icon for "{}" app:'.format(self.app))
            layout.addWidget(label, 0, 0, 1, 3)

        self.customIconItem = None
        iconModel = QtGui.QStandardItemModel()
        self.iconCombo = QtGui.QComboBox()
        self.iconCombo.setModel(iconModel)
        self.iconCombo.setItemDelegate(IconDelegate(self.iconCombo))

        self.noIconItem = QtGui.QStandardItem()
        self.noIconItem.setData(emptyIcon(), QtCore.Qt.DecorationRole)
        self.noIconItem.setData('No icon', IconDisplayRole)
        self.noIconItem.setData('', IconNameRole)
        iconModel.appendRow(self.noIconItem)

        self.settings.beginGroup('customIcons')
        iconItems = {}
        if self.settings.childKeys():
            customIconsHeaderRow = iconModel.rowCount()
            customExist = False
            for app in self.settings.childKeys():
                app = unicode(app)
                customValue = unicode(self.settings.value(app).toPyObject())
                if not customValue or customValue == 'false':
                    continue
                customExist = True
                item = QtGui.QStandardItem()
                if customValue != 'true' and customValue in self.main.defaultIcons:
                    icon = self.main.defaultIcons[customValue]
                else:
                    icon = QtGui.QIcon('{}/{}.png'.format(self.main.iconsPath, app))
                item.setData(icon, QtCore.Qt.DecorationRole)
                item.setData(app, IconDisplayRole)
                item.setData(app, IconNameRole)
                iconModel.appendRow(item)
                iconItems[app] = item
            if customExist:
                customIconsHeader = QtGui.QStandardItem()
                customIconsHeader.setData('Custom icons:', IconDisplayRole)
                customIconsHeader.setEnabled(False)
                iconModel.insertRow(customIconsHeaderRow, customIconsHeader)

        defaultIconsHeader = QtGui.QStandardItem()
        defaultIconsHeader.setData('Default icons:', IconDisplayRole)
        defaultIconsHeader.setEnabled(False)
        iconModel.appendRow(defaultIconsHeader)
        defaultIconItems = {}
        for appName in sorted(self.main.defaultIcons.keys()):
            icon = self.main.defaultIcons[appName]
            item = QtGui.QStandardItem()
            item.setData(icon, QtCore.Qt.DecorationRole)
            item.setData(appName, IconDisplayRole)
            item.setData('{}.png'.format(appName), IconNameRole)
            iconModel.appendRow(item)
            defaultIconItems[appName] = item
            if self.app == appName:
                item.setData(True, DefaultIconRole)

        self.iconName = self.settings.value(self.app).toString()
        if self.iconName == 'false':
            self.currentItem = self.noIconItem
        elif self.iconName:
            try:
                self.currentItem = iconItems[self.app]
            except Exception as e:
                print e
                self.currentItem = self.noIconItem
        else:
            try:
                self.currentItem = defaultIconItems[self.app]
            except:
                self.currentItem = self.noIconItem
            self.currentItem.setData(True, DefaultIconRole)
        self.settings.endGroup()
        self.previousItem = self.currentItem
        self.iconCombo.setCurrentIndex(self.iconCombo.model().indexFromItem(self.currentItem).row())
        self.iconCombo.currentIndexChanged.connect(self.setCurrentIndex)

        layout.addWidget(self.iconCombo, 1, 1 if editable else 0)

        if editable:
            spacer = QtGui.QFrame()
            spacer.setFrameShape(spacer.VLine)
            spacer.setFrameShadow(spacer.Sunken)
            layout.addWidget(spacer, 1, 2)

        browseBtn = QtGui.QPushButton()
        browseBtn.setToolTip('Browse for icon...')
        browseBtn.setIcon(self.style().standardIcon(QtGui.QStyle.SP_DialogOpenButton))
        browseBtn.clicked.connect(self.browse)
        layout.addWidget(browseBtn, 1, 3 if editable else 2)
        self.clearBtn = QtGui.QPushButton()
        self.clearBtn.setEnabled(True if self.currentItem != self.noIconItem else False)
        self.clearBtn.setToolTip('Clear icon')
        self.clearBtn.setIcon(self.style().standardIcon(QtGui.QStyle.SP_DialogCloseButton))
        self.clearBtn.clicked.connect(self.clear)
        layout.addWidget(self.clearBtn, 1, 4 if editable else 3)

        self.buttonBox = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok|QtGui.QDialogButtonBox.Cancel)
        self.buttonBox.button(QtGui.QDialogButtonBox.Cancel).clicked.connect(self.reject)
        self.buttonBox.button(QtGui.QDialogButtonBox.Ok).clicked.connect(self.accept)
        layout.addWidget(self.buttonBox, 2, 0, 1, layout.columnCount())

    def setCurrentIndex(self, i):
        self.currentItem = self.iconCombo.model().item(i, 0)
        self.iconChanged = True if self.previousItem != self.currentItem else False
        if self.currentItem != self.noIconItem:
            self.iconName = unicode(self.currentItem.data(IconNameRole).toPyObject())
            self.clearBtn.setEnabled(True)
        else:
            self.iconName = 'noicon'
            self.clearBtn.setEnabled(False)

    def appEditChanged(self, text):
        if text != self.app:
            if unicode(text) in self.appList:
                self.buttonBox.button(QtGui.QDialogButtonBox.Ok).setEnabled(False)
                self.appEdit.setStyleSheet('color: red;')
            else:
                self.buttonBox.button(QtGui.QDialogButtonBox.Ok).setEnabled(True)
                self.appEdit.setStyleSheet('')
            self.appChanged = True
        else:
            self.buttonBox.button(QtGui.QDialogButtonBox.Ok).setEnabled(True)
            self.appEdit.setStyleSheet('')
            self.appChanged = False

    def browse(self):
        iconName = QtGui.QFileDialog.getOpenFileName(self, 
            u'Select icon for "{}" app'.format(self.app), 
            os.path.dirname(__file__),
            'Images (*.png *.svg *.jpg)'
            )
        if not iconName:
            return
        try:
#            icon = QtGui.QPixmap(iconName).scaled(QtCore.QSize(12, 12), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
#            self.iconLabel.setToolTip(os.path.basename(unicode(iconName)))
#            self.iconLabel.setPixmap(icon)
            if iconName != self.iconName:
                icon = QtGui.QPixmap(iconName)
                if icon.width() > 12 or icon.height() > 12:
                    icon = icon.scaled(QtCore.QSize(12, 12), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                if not self.customIconItem:
                    iconItem = QtGui.QStandardItem()
                    self.iconCombo.model().insertRow(0, iconItem)
                else:
                    iconItem = self.customIconItem
                iconItem.setData(icon, QtCore.Qt.DecorationRole)
                iconItem.setData(iconName, IconNameRole)
                self.iconName = iconName
                self.iconCombo.setCurrentIndex(0)
#                self.iconChanged = True
            self.clearBtn.setEnabled(True)
        except Exception as e:
            print e

    def clear(self):
        self.iconName = ''
        self.iconChanged = True
        self.clearBtn.setEnabled(False)
        self.iconCombo.setCurrentIndex(self.iconCombo.model().indexFromItem(self.noIconItem).row())
#        self.iconLabel.setToolTip('No image selected')
#        self.iconLabel.setPixmap(self.emptyIcon())


class BatteryLogGraphicsObject(QtGui.QGraphicsObject):
    activated = QtCore.pyqtSignal(int)
    def __init__(self, id, pos, alpha, beta):
        self.id = id
        self.pen = QtCore.Qt.NoPen
        QtGui.QGraphicsObject.__init__(self)
        npos = pos + beta.time - alpha.time
        self.poly = QtGui.QPolygonF([
                QtCore.QPoint(pos, 100), 
                QtCore.QPoint(pos, 100 - alpha.battery), 
                QtCore.QPoint(npos, 100 - beta.battery), 
                QtCore.QPoint(npos, 100), 
                QtCore.QPoint(pos, 100)
            ])
        if not alpha.reachable:
            self.grad = QtCore.Qt.gray
        else:
            self.grad = QtGui.QLinearGradient(pos, 0, npos, 0)
            startColor = QtGui.QColor(*batteryColor(alpha.battery)) 
            endColor = QtGui.QColor(*batteryColor(beta.battery))
            if not alpha.charging:
                startColor.setAlpha(127)
                endColor.setAlpha(127)
            self.grad.setColorAt(0, startColor)
            self.grad.setColorAt(1, endColor)
        self.setToolTip('{date}: {state}'.format(
            date=QtCore.QDateTime.fromMSecsSinceEpoch(alpha.time * 1000).toString('dd/MM/yy hh:mm'), 
            state='{battery}% {charging}'.format(
                battery=alpha.battery, 
                charging=' (charging)' if alpha.charging else ''
                ) if alpha.reachable else 'Offline'
            ))
        self.pos = pos
        self.npos = npos

    def boundingRect(self):
        return self.poly.boundingRect()

    def paint(self, qp, *args, **kwargs):
        qp.setPen(self.pen)
        qp.setBrush(self.grad)
        qp.drawPolygon(self.poly)

    def mousePressEvent(self, event):
        self.activated.emit(self.id)


class StatusScene(QtGui.QGraphicsScene):
    itemClicked = QtCore.pyqtSignal(int)
    def __init__(self):
        QtGui.QGraphicsScene.__init__(self)
        self.statusHistory = []
        self.activeItem = None
        self.items = []
        self.dateLinePen = QtGui.QPen(QtCore.Qt.darkBlue)
        self.dateLinePen.setStyle(QtCore.Qt.DotLine)

    def updateData(self, data):
        if len(self.statusHistory) == len(data) or len(data) <= 2:
            return
        self.statusHistory = data[:]
        self.clear()

        iterData = iter(data)
        alpha = iterData.next()
        pos = 0
        id = 0
        while True:
            try:
#                print alpha
                beta = iterData.next()
                item = BatteryLogGraphicsObject(id, pos, alpha, beta)
                item.activated.connect(self.itemClicked)
                item.activated.connect(self.itemActivated)
                self.items.append(item)
                self.addItem(item)
                id += 1
                alpha = beta
                pos = item.npos
            except Exception as e:
                print e
                break
        self.addRect(0, 0, item.npos, 100, QtGui.QPen(QtCore.Qt.NoPen))
        firstDate = QtCore.QDateTime.fromMSecsSinceEpoch(data[0].time * 1000)
        nextDate = QtCore.QDateTime(firstDate.date().addDays(1), QtCore.QTime(0, 0))
        nextSecs = firstDate.secsTo(nextDate)
        lastDate = QtCore.QDateTime.fromMSecsSinceEpoch(data[-1].time * 1000)
        lastSecs = firstDate.secsTo(QtCore.QDateTime(lastDate.date(), QtCore.QTime(0, 0)))
#        print firstDate, nextDate, nextSecs, lastSecs
        while nextSecs <= lastSecs:
            self.addLine(nextSecs, 0, nextSecs, 100, self.dateLinePen)
            dateText = self.addText(nextDate.toString('dd/MM/yy'))
            dateText.setX(nextSecs)
            dateText.setFlag(dateText.ItemIgnoresTransformations, True)
            nextSecs += 86400
            nextDate = nextDate.addDays(1)
#        print self.views()
            
        firstDateText = self.addText(firstDate.toString('dd/MM/yy'))
        firstDateText.setFlag(firstDateText.ItemIgnoresTransformations, True)

    def itemActivated(self, id):
        old = self.activeItem
        if old is not None:
            old.pen = QtCore.Qt.NoPen
            old.update
        self.activeItem = self.items[id]
        self.activeItem.pen = QtCore.Qt.blue
        self.update()


class HistoryDialog(QtGui.QDialog):
    def __init__(self, main):
        QtGui.QDialog.__init__(self)
        uic.loadUi('history.ui', self)
        self.main = main
        self.settings = self.main.settings
#        self.historySplitter.splitterMoved.connect(self.splitterResized)
        self.notificationsHistoryModel = QtGui.QStandardItemModel()
        self.notificationsHistoryProxyModel = QtGui.QSortFilterProxyModel()
        self.notificationsHistoryProxyModel.setSourceModel(self.notificationsHistoryModel)
        self.notificationsHistoryProxyModel.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.statusModel = QtGui.QStandardItemModel()
        self.notificationTable.setModel(self.notificationsHistoryProxyModel)
        self.statusTable.setModel(self.statusModel)
        self.statusTable.clicked.connect(self.itemActivated)
#        self.statusTable.horizontalHeader().setResizeMode(1, QtGui.QHeaderView.Fixed)
#        self.statusTable.horizontalHeader().resizeSection(1, 20)
        self.notificationTable.customContextMenuRequested.connect(self.notificationTableMenu)
        self.notificationsHistory = []
        self.statusHistory = []
        self.statusScene = StatusScene()
        self.statusView.setScene(self.statusScene)
        self.statusScene.itemClicked.connect(self.statusTable.selectRow)
        self.statusView.resizeEvent = lambda event: self.statusView.fitInView(self.statusScene.sceneRect())
        self.statusIcons = [QtGui.QIcon(OfflineLed()), QtGui.QIcon(OnlineLed())]
        self.filterCombo.currentIndexChanged.connect(self.filterTypeChanged)

        self.filterEditWidget = QtGui.QWidget()
        hlayout = QtGui.QHBoxLayout()
        self.filterEditWidget.setLayout(hlayout)

        self.filterEdit = QtGui.QLineEdit()
        self.filterCompleter = QtGui.QCompleter(self.notificationsHistoryProxyModel, self)
        self.filterEdit.setCompleter(self.filterCompleter)
        self.filterCompleter.setCompletionMode(self.filterCompleter.InlineCompletion)
        self.filterEdit.textChanged.connect(self.filterTextChanged)
        self.filterEdit.installEventFilter(self)
        hlayout.addWidget(self.filterEdit)
        self.filterEditClearBtn = QtGui.QPushButton()
        self.filterEditClearBtn.setFocusPolicy(QtCore.Qt.NoFocus)
        self.filterEditClearBtn.setEnabled(False)
        self.filterEditClearBtn.setIcon(self.style().standardIcon(QtGui.QStyle.SP_DialogCloseButton))
        self.filterEditClearBtn.clicked.connect(lambda: self.filterEdit.setText(''))
        hlayout.addWidget(self.filterEditClearBtn)

        self.stackedWidget = QtGui.QWidget()
        self.horizontalLayout.addWidget(self.stackedWidget)
        self.stackedWidget.setSizePolicy(QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Maximum))
        self.stackedLayout = QtGui.QStackedLayout()
        self.stackedWidget.setLayout(self.stackedLayout)
        self.stackedLayout.addWidget(self.filterEditWidget)

        self.singleDateEditWidget = QtGui.QWidget()
        self.singleDateEditWidget.setSizePolicy(QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Maximum))
        hlayout = QtGui.QHBoxLayout()
        hlayout.setContentsMargins(0, 0, 0, 0)
        self.singleDateEditWidget.setLayout(hlayout)
        self.singleDateEdit = QtGui.QDateEdit()
        self.singleDateEdit.setDate(QtCore.QDate.currentDate())
        self.singleDateEdit.dateChanged.connect(self.filterSingleDateChanged)
        self.singleDateEdit.setCalendarPopup(True)
        hlayout.addWidget(self.singleDateEdit)
        spacer = QtGui.QWidget()
        spacer.setSizePolicy(QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Maximum))
        hlayout.addWidget(spacer)
        self.stackedLayout.addWidget(self.singleDateEditWidget)

        self.rangeDateEditWidget = QtGui.QWidget()
        self.rangeDateEditWidget.setSizePolicy(QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Maximum))
        hlayout = QtGui.QHBoxLayout()
        hlayout.setContentsMargins(0, 0, 0, 0)
#        hlayout.setSizeConstraint(hlayout.SetFixedSize)
        self.rangeDateEditWidget.setLayout(hlayout)
        self.startRangeDateEdit = QtGui.QDateEdit()
        self.startRangeDateEdit.dateChanged.connect(lambda date, sender=STARTDATE: self.checkDateRange(date, sender))
        self.startRangeDateEdit.setCalendarPopup(True)
        self.endRangeDateEdit = QtGui.QDateEdit()
        self.endRangeDateEdit.setDate(QtCore.QDate.currentDate())
        self.endRangeDateEdit.dateChanged.connect(lambda date, sender=ENDDATE: self.checkDateRange(date, sender))
        self.endRangeDateEdit.setCalendarPopup(True)
        hlayout.addWidget(QtGui.QLabel('from'))
        hlayout.addWidget(self.startRangeDateEdit)
        hlayout.addWidget(QtGui.QLabel('to'))
        hlayout.addWidget(self.endRangeDateEdit)
        self.stackedLayout.addWidget(self.rangeDateEditWidget)

        self.computeStatsBtn.clicked.connect(self.computeStats)

    def computeStats(self):
        if not self.statusHistory:
            return
        offline = 0
        online = 0
        states = iter(self.statusHistory)
        alpha = states.next()
        while True:
            try:
                beta = states.next()
                if alpha.reachable:
                    online += beta.time - alpha.time
                else:
                    offline += beta.time - alpha.time
                alpha = beta
            except:
                break
        onlineStr = simpleTimeFormat(online)
        self.onlineTimeLineEdit.setText(onlineStr)
        offlineStr = simpleTimeFormat(offline)
        self.offlineTimeLineEdit.setText(offlineStr)
        width = max(self.fontMetrics().width(onlineStr), self.fontMetrics().width(offlineStr))
        self.onlineTimeLineEdit.setMinimumWidth(width + self.style().pixelMetric(QtGui.QStyle.PM_DefaultFrameWidth) * 2)

    def itemActivated(self, index):
        self.statusScene.itemActivated(index.row())

    def eventFilter(self, source, event):
        if source == self.filterEdit and event.type() == QtCore.QEvent.KeyPress:
            if event.key() == QtCore.Qt.Key_Escape and self.filterEdit.text() != '':
                self.filterEdit.setText('')
                return True
        return QtGui.QDialog.eventFilter(self, source, event)

    def filterSingleDateChanged(self, date):
#        TODO: use filter role and add custom role for date format
        self.notificationsHistoryProxyModel.invalidateFilter()
        self.notificationsHistoryProxyModel.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.notificationsHistoryProxyModel.setFilterKeyColumn(2)
        self.notificationsHistoryProxyModel.setFilterWildcard(date.toString('ddd MMM dd'))

    def filterRangeDateChanged(self, first, last):
        self.notificationsHistoryProxyModel.invalidateFilter()
        self.notificationsHistoryProxyModel.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.notificationsHistoryProxyModel.setFilterKeyColumn(2)
        dates = []
        date = QtCore.QDate(first)
        while date <= last:
            dates.append(u'({})'.format(date.toString('ddd MMM dd')))
            date = date.addDays(1)
        self.notificationsHistoryProxyModel.setFilterRegExp(QtCore.QRegExp(u'|'.join(dates)))

    def checkDateRange(self, date, sender):
        if sender == STARTDATE:
            self.endRangeDateEdit.setMinimumDate(date)
        elif sender == ENDDATE:
            self.startRangeDateEdit.setMaximumDate(date)
        if self.stackedLayout.currentIndex() == 2:
            self.filterRangeDateChanged(self.startRangeDateEdit.date(), self.endRangeDateEdit.date())

    def filterTextChanged(self, text):
        if not text:
            self.filterEditClearBtn.setEnabled(False)
            self.notificationsHistoryProxyModel.setFilterKeyColumn(-1)
        else:
            self.filterEditClearBtn.setEnabled(True)
            self.notificationsHistoryProxyModel.setFilterKeyColumn(self.filterCombo.currentIndex() - 1)
        self.notificationsHistoryProxyModel.invalidateFilter()
        self.notificationsHistoryProxyModel.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.notificationsHistoryProxyModel.setFilterWildcard(text)

    def filterTypeChanged(self, filterId):
        if filterId <= 3:
            self.notificationsHistoryProxyModel.invalidateFilter()
            self.notificationsHistoryProxyModel.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
            self.filterTextChanged(self.filterEdit.text())
            self.filterCompleter.setCompletionColumn(filterId - 1 if filterId else 0)
            self.notificationsHistoryProxyModel.setFilterKeyColumn(filterId - 1)
            self.stackedLayout.setCurrentIndex(0)
        elif filterId == 4:
            self.notificationsHistoryProxyModel.invalidateFilter()
            self.notificationsHistoryProxyModel.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
            self.stackedLayout.setCurrentIndex(1)
            self.filterSingleDateChanged(self.singleDateEdit.date())
        else:
            self.notificationsHistoryProxyModel.invalidateFilter()
            self.stackedLayout.setCurrentIndex(2)
            self.filterRangeDateChanged(self.startRangeDateEdit.date(), self.endRangeDateEdit.date())

    def notificationTableMenu(self, pos):
        index = self.notificationTable.indexAt(pos)
        menu = QtGui.QMenu(self)
        appIndex = index.sibling(index.row(), 0)
        tickerIndex = index.sibling(index.row(), 1)
        timeIndex = index.sibling(index.row(), 2)
        app = unicode(appIndex.data().toString())
        copyAction = QtGui.QAction('Copy notification text', self)
        copyNotificationAction = QtGui.QAction('Copy notification info', self)
        sep = QtGui.QAction(self)
        sep.setSeparator(True)
        allSameAction = QtGui.QAction('Select all "{}" notifications'.format(app), menu)
        iconEditAction = QtGui.QAction('Edit icon for "{}"...'.format(app), menu)
        menu.addActions([copyAction, copyNotificationAction, sep, allSameAction, iconEditAction])
        res = menu.exec_(self.notificationTable.viewport().mapToGlobal(pos))
        if not res:
            return
        elif res == copyAction:
            QtGui.QApplication.clipboard().setText(tickerIndex.data().toPyObject())
        elif res == copyNotificationAction:
            print timeIndex.data(TimeRole).toPyObject()
            QtGui.QApplication.clipboard().setText(
                u'{app} ({date}): {ticker}'.format(
                    app=app, 
                    date=QtCore.QDateTime.fromMSecsSinceEpoch(timeIndex.data(TimeRole).toPyObject() * 1000).toString('dd/MM/yy hh:mm:ss'), 
                    ticker=tickerIndex.data().toPyObject()
                    )
                )
        elif res == allSameAction:
            items = self.notificationsHistoryModel.match(appIndex, QtCore.Qt.DisplayRole, appIndex.data(), -1, QtCore.Qt.MatchExactly|QtCore.Qt.MatchWrap)
            selection = self.notificationTable.selectionModel().selection()
            for item in items:
                selection.select(item, item.sibling(item.row(), 2))
            self.notificationTable.selectionModel().select(selection, QtGui.QItemSelectionModel.Select)
        elif res == iconEditAction:
            dialog = IconEditDialog(self, app)
            if not dialog.exec_():
                return
            if dialog.iconChanged:
                iconName = unicode(dialog.iconName)
                if not iconName or iconName == 'noicon':
                    for appIndex in self.notificationsHistoryModel.match(appIndex, QtCore.Qt.DisplayRole, appIndex.data(), -1, QtCore.Qt.MatchExactly|QtCore.Qt.MatchWrap):
                        appItem = self.notificationsHistoryModel.itemFromIndex(appIndex)
                        appItem.setData(None, QtCore.Qt.DecorationRole)
                        appItem.setData(QtGui.QBrush(QtCore.Qt.white), QtCore.Qt.BackgroundRole)
                    self.settings.beginGroup('customIcons')
                    if app in self.main.defaultIcons:
                        self.settings.setValue(app, 'false')
                    elif app in self.settings.childKeys():
                        self.settings.remove(app)
                    QtCore.QFile('{}/{}.png'.format(self.main.iconsPath, app)).remove()
                    self.settings.endGroup()
                    self.settings.sync()
                    return
                pm = dialog.currentItem.data(QtCore.Qt.DecorationRole).toPyObject()
                for appIndex in self.notificationsHistoryModel.match(appIndex, QtCore.Qt.DisplayRole, appIndex.data(), -1, QtCore.Qt.MatchExactly|QtCore.Qt.MatchWrap):
                    appItem = self.notificationsHistoryModel.itemFromIndex(appIndex)
                    appItem.setData(pm, QtCore.Qt.DecorationRole)
                    appItem.setData(QtGui.QBrush(QtCore.Qt.lightGray), QtCore.Qt.BackgroundRole)
                self.settings.beginGroup('customIcons')
                if dialog.currentItem.data(DefaultIconRole).toPyObject():
                    dest = QtCore.QFile(u'{}/{}.png'.format(self.main.iconsPath, app))
                    if dest.exists():
                        dest.remove()
                    self.settings.remove(app)
                elif iconName.startswith('/'):
                    saveIcon(iconName, unicode(app))
                    self.settings.setValue(app, 'true')
                else:
                    dest = QtCore.QFile(u'{}/{}.png'.format(self.main.iconsPath, app))
                    if dest.exists():
                        dest.remove()
                    QtCore.QFile.copy(os.path.join(os.path.dirname(__file__), 'icons', iconName), dest.fileName())
                    self.settings.setValue(app, iconName[:-4])
                self.settings.endGroup()
                self.settings.sync()
                return
#                if pm.size().width() > 12 or pm.size().height() > 12:
#                    pm = pm.scaled(QtCore.QSize(12, 12), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
#                    imgpath = iconName if iconName.startswith('/') else os.path.join(os.path.dirname(__file__), iconName)
#                    if not imgpath.endswith('.png'):
#                        imgpath += '.png'
#                    pm.save(imgpath)
#                else:
#                    imgpath = iconName if iconName.startswith('/') else os.path.join(os.path.dirname(__file__), iconName)
#                    if os.path.dirname(imgpath) != os.path.dirname(__file__):
#                        QtCore.QFile.copy(imgpath, os.path.join(os.path.dirname(__file__), os.path.basename(imgpath)))
#                self.settings.beginGroup('customIcons')
#                self.settings.setValue(app, True)
#                self.settings.endGroup()
#                self.settings.sync()

    def resizeEvent(self, event):
        self.statusTable.setMinimumHeight(self.height() - 250)
        self.statusTable.setMinimumHeight(150)

    def showEvent(self, event):
        self.filterEdit.setFocus(QtCore.Qt.OtherFocusReason)
        if len(self.notificationsHistory) != len(self.main.notificationsHistory):
            self.notificationsHistoryRefresh(True)
            self.notificationTable.scrollToBottom()
        if len(self.statusHistory) != len(self.main.statusHistory):
            self.statusRefresh(True)
            self.statusTable.scrollToBottom()
        if self.notificationsHistory:
            for cal in (self.singleDateEdit, self.startRangeDateEdit, self.endRangeDateEdit):
                cal.setMinimumDate(QtCore.QDateTime.fromMSecsSinceEpoch(self.notificationsHistory[0].time * 1000).date())
                cal.setMaximumDate(QtCore.QDate.currentDate())

    def statusRefresh(self, reload=False):
        if not self.statusHistory or reload:
            states = self.main.statusHistory[:]
            self.statusHistory = states
            self.statusModel.clear()
        else:
            states = self.main.statusHistory[len(self.statusHistory):]
            self.statusHistory.extend(states)
        self.statusModel.setHorizontalHeaderLabels(['Date/Time', 'Battery', 'Charging'])
        for state in states:
            time = QtCore.QDateTime.fromMSecsSinceEpoch(state.time * 1000)
            timeItem = QtGui.QStandardItem(time.toString('dd/MM/yy hh:mm:ss'))
            timeItem.setData(time.toString('dddd d MMMM yyyy, hh:mm:ss'), QtCore.Qt.ToolTipRole)
            timeItem.setData(self.statusIcons[state.reachable], QtCore.Qt.DecorationRole)
            batteryItem = QtGui.QStandardItem('{}%'.format(state.battery))
            batteryItem.setData(QtGui.QColor(*batteryColor(state.battery)), QtCore.Qt.ForegroundRole)
            batteryItem.setData(QtCore.Qt.AlignCenter, QtCore.Qt.TextAlignmentRole)
            chargingItem = QtGui.QStandardItem(str(state.charging))
            chargingItem.setData(QtCore.Qt.AlignCenter, QtCore.Qt.TextAlignmentRole)
            self.statusModel.appendRow([timeItem, batteryItem, chargingItem])
        if not self.statusHistory:
            return
        self.startTimeLineEdit.setText(
            QtCore.QDateTime.fromMSecsSinceEpoch(self.statusHistory[0].time * 1000).toString('dd/MM/yy hh:mm:ss'))
        self.endTimeLineEdit.setText(
            QtCore.QDateTime.fromMSecsSinceEpoch(self.statusHistory[-1].time * 1000).toString('dd/MM/yy hh:mm:ss'))
        self.statusTable.resizeColumnsToContents()
        self.statusTable.resizeRowsToContents()
        self.statusTable.horizontalHeader().setResizeMode(0, QtGui.QHeaderView.Fixed)
        self.statusTable.horizontalHeader().setResizeMode(1, QtGui.QHeaderView.Fixed)
        self.statusTable.horizontalHeader().setResizeMode(2, QtGui.QHeaderView.Fixed)
        self.statusScene.updateData(self.statusHistory)
        self.statusView.fitInView(self.statusScene.sceneRect())
        QtCore.QTimer.singleShot(0, lambda: self.statusTable.setFixedWidth(
            self.statusTable.verticalScrollBar().width() + \
            self.statusTable.lineWidth() * 2 + \
            self.statusTable.frameWidth() * 2 + \
            sum(self.statusTable.columnWidth(c) for c in xrange(self.statusModel.columnCount()))
            ))

    def notificationsHistoryRefresh(self, reload=False):
        if not self.notificationsHistory or reload:
            cache = self.main.notificationsHistory[:] 
            self.notificationsHistory = cache
            self.notificationsHistoryModel.clear()
        else:
            cache = self.main.notificationsHistory[len(self.notificationsHistory):]
            self.notificationsHistory.extend(cache)
        self.notificationsHistoryModel.setHorizontalHeaderLabels(['App', 'Text', 'Date'])
        self.settings.beginGroup('customIcons')
        for time, app, ticker, id in cache:
            appItem = QtGui.QStandardItem(app)
            iconName = self.settings.value(app).toString()
            if iconName == 'noicon':
                pass
            elif iconName:
                appItem.setData(QtGui.QIcon('{}/{}'.format(self.main.iconsPath, app)), QtCore.Qt.DecorationRole)
                appItem.setData(QtGui.QBrush(QtCore.Qt.lightGray), QtCore.Qt.BackgroundRole)
            elif app in self.main.defaultIcons:
                appItem.setData(self.main.defaultIcons[app], QtCore.Qt.DecorationRole)
                appItem.setData(QtGui.QBrush(QtCore.Qt.lightGray), QtCore.Qt.BackgroundRole)
            textItem = QtGui.QStandardItem(ticker)
            textItem.setData(ticker, QtCore.Qt.ToolTipRole)
            timeItem = QtGui.QStandardItem(QtCore.QDateTime.fromMSecsSinceEpoch(time * 1000).toString())
            timeItem.setData(time, TimeRole)
            self.notificationsHistoryModel.appendRow([appItem, textItem, timeItem])
        self.settings.endGroup()
        self.notificationTable.resizeColumnToContents(0)
        self.notificationTable.resizeColumnToContents(2)
        self.notificationTable.horizontalHeader().setResizeMode(1, QtGui.QHeaderView.Stretch)
        self.notificationTable.horizontalHeader().setResizeMode(2, QtGui.QHeaderView.Fixed)
        self.notificationTable.resizeRowsToContents()
#        self.resize(400, self.height())


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
            icon = _icons[icon]
        elif icon.startswith('/') or icon.endswith('.png'):
            icon = 'file://' + icon
        self.queue.put((priority, (title, body, icon, timeout)))

    def quit(self):
        self.queue.put((0, -1))


class MissingRequiredPluginDialog(QtGui.QDialog):
    def __init__(self, main):
        QtGui.QDialog.__init__(self)
        self.setModal(True)
        self.main = main
        layout = QtGui.QGridLayout()
        self.setLayout(layout)
        layout.addWidget(QtGui.QLabel(
            'The following KdeConnect plugins have been disabled.\n' \
            'Press "Restore" to enable them again.\n' \
            'Pressing "Cancel" will result in unexpected behavior.'
            ))
        self.pluginsTable = QtGui.QListView()
        layout.addWidget(self.pluginsTable)
        self.pluginsModel = QtGui.QStandardItemModel()
        self.pluginsTable.setModel(self.pluginsModel)
        self.pluginsTable.setSizePolicy(QtGui.QSizePolicy(QtGui.QSizePolicy.Maximum, QtGui.QSizePolicy.Preferred))
        self.pluginsTable.setSelectionMode(self.pluginsTable.NoSelection)
        self.pluginsTable.setEditTriggers(self.pluginsTable.NoEditTriggers)

        self.buttonBox = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Cancel)
        self.restoreBtn = QtGui.QPushButton('Restore')
        self.restoreBtn.setIcon(QtGui.QIcon.fromTheme('edit-undo'))
        self.buttonBox.addButton(self.restoreBtn, self.buttonBox.AcceptRole)
        layout.addWidget(self.buttonBox)
        self.restoreBtn.clicked.connect(self.restorePlugins)

    def restorePlugins(self):
        self.settings = QtCore.QSettings(self.phone.devIface.pluginsConfigFile(), QtCore.QSettings.NativeFormat)
        self.settings.beginGroup('plugins')
        for missing in KdeConnectRequiredPlugins & set(map(unicode, self.phone.devIface.loadedPlugins())) ^ KdeConnectRequiredPlugins:
            self.settings.setValue('{}Enabled'.format(missing), True)
        self.settings.endGroup()
        self.settings.sync()
        self.phone.devIface.reloadPlugins()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            event.accept()
        else:
            QtGui.QDialog.keyPressEvent(self, event)

    def closeEvent(self, event):
        event.ignore()

    def updatePlugins(self, state=None):
        self.phone = self.main.phone
        if state is None:
            state = self.phone.hasMissingRequiredPlugins()
            print state
        if not state:
            self.hide()
            return
        _start = self.pluginsModel.index(0, 0)
        missingPlugins = KdeConnectRequiredPlugins & set(map(unicode, self.phone.devIface.loadedPlugins())) ^ KdeConnectRequiredPlugins
        for missing in missingPlugins:
            matches = self.pluginsModel.match(_start, PluginRole, missing, -1, QtCore.Qt.MatchExactly|QtCore.Qt.MatchWrap)
            if not matches:
                missingItem = QtGui.QStandardItem(KdeConnectPlugins[missing].text)
                missingItem.setData(missing, PluginRole)
                self.pluginsModel.appendRow(missingItem)
        for plugin in KdeConnectRequiredPlugins:
            if plugin not in missingPlugins:
                matches = self.pluginsModel.match(_start, PluginRole, plugin, -1, QtCore.Qt.MatchExactly|QtCore.Qt.MatchWrap)
                if matches:
                    self.pluginsModel.takeRow(matches[0].row())

        if not self.isVisible():
            showCenter(self)
            self.pluginsTable.setMaximumHeight(self.pluginsTable.sizeHintForRow(0) * len(KdeConnectRequiredPlugins) + self.pluginsTable.frameWidth() * 2)
            self.adjustSize()

    def exec_(self):
        self.pluginsModel.clear()
        self.phone = self.main.phone
        for missing in KdeConnectRequiredPlugins & set(map(unicode, self.phone.devIface.loadedPlugins())) ^ KdeConnectRequiredPlugins:
            missingItem = QtGui.QStandardItem(KdeConnectPlugins[missing].text)
            self.pluginsModel.appendRow(missingItem)
        self.show()
        self.pluginsTable.setMaximumHeight(self.pluginsTable.sizeHintForRow(0) * len(KdeConnectRequiredPlugins) + self.pluginsTable.frameWidth() * 2)
        self.adjustSize()


class KdeConnect(QtGui.QSystemTrayIcon):
    def __init__(self, parent, deviceID):
        self.iconOff = QtGui.QIcon('kdeconnect-tray-off.svg')
        QtGui.QSystemTrayIcon.__init__(self, self.iconOff, parent)
        self.phone = Device(deviceID)
        self.notifier = DBusNotificationsManager(self)
        self.notifierThread = QtCore.QThread()
        self.notifier.moveToThread(self.notifierThread)
        self.notifierThread.started.connect(self.notifier.run)
        self.notifier.finished.connect(self.notifierThread.quit)
        self.startUpTimer = QtCore.QElapsedTimer()
        self.startUpTimer.start()
        self.settings = QSettings()
        self.settings.setValue('deviceID', deviceID)
        self.settings.changed.connect(self.setChargeAlerts)
        self.notifyBatteryChargeAlertIntervals = map(int, self.settings.value(
            'notifyBatteryChargeAlertIntervals', 
            settingsWidgets['notifyBatteryChargeAlertIntervals'].default).toPyObject().split(','))
        self.notifyBatteryDischargeAlertIntervals = map(int, self.settings.value(
            'notifyBatteryDischargeAlertIntervals', 
            settingsWidgets['notifyBatteryDischargeAlertIntervals'].default).toPyObject().split(','))

        self.historyDialog = HistoryDialog(self)
        self.settingsDialog = SettingsDialog(self)
        self.missingRequiredPluginDialog = MissingRequiredPluginDialog(self)
        self.loadData()
        self.createMenu()
        self.dbus = dbus.SessionBus()
        self.fd_proxy = self.dbus.get_object('org.freedesktop.DBus', '/org/freedesktop/DBus')
        self.fd_iface = dbus.Interface(self.fd_proxy, dbus_interface='org.freedesktop.DBus')
        self.iconOn = CustomIcon(self.phone)
        self.phone.reachableChanged.connect(self.reachableChanged)
        self.phone.batteryChanged.connect(self.updatePhone)
        self.phone.batteryChanged.connect(self.updateStatus)
        self.phone.chargeStateChanged.connect(self.updatePhone)
        self.phone.chargeStateChanged.connect(self.updateStatus)
        self.phone.notificationsChanged.connect(self.updatePhone)
        self.phone.newNotification.connect(self.updateCache)
        self.phone.missingRequiredPlugin.connect(self.missingRequiredPluginDialog.updatePlugins)

#        self.phone.reachableChanged.connect(self.testReachable)
#        self.phone.batteryChanged.connect(self.testBattery)
#        self.phone.chargeStateChanged.connect(self.testCharge)

        self.installEventFilter(self)
        self.tooltipWidget = ToolTipWidget(self, self.phone)
        self.setToolTip('')
        self.defaultIcons = {}
        for _iconPath in glob('icons/*'):
                _iconName = os.path.basename(_iconPath)
                self.defaultIcons[_iconName[:-4]] = QtGui.QIcon(_iconPath)
        self.notifierThread.start()
        self.notifier.notify(body='Started!')
#        QtCore.QTimer.singleShot(1000, self.missingRequiredPluginDialog.updatePlugins)
        QtCore.QTimer.singleShot(1000, self.missingRequiredPluginDialog.updatePlugins)
        self.iconBlinkTimer = DualTimer(self)
        self.iconBlinkTimer.setIntervals(250, 750)
        self.iconBlinkTimer.timeoutDual.connect(self.setCurrentIcon)
        self._currentIcon = self.iconOff


#        self.fd_iface.connect_to_signal('NameOwnerChanged', self.owner_changed)

    def timeoutShow(self, *args):
        print args

    def testBattery(self, battery):
        print 'battery changed:', battery
    def testCharge(self, state):
        print 'charge changed:', state
    def testReachable(self, state):
        print 'reachable changed:', state


    def getDataDir(self):
        self.dataDir = getDataDir()
        if not self.dataDir:
            return self.dataDir
        self.notificationsHistoryPath = self.dataDir + '/{}.cache'.format(self.phone.id)
        self.statusPath = self.dataDir + '/{}.status'.format(self.phone.id)
        self.iconsPath = self.dataDir + '/icons'
        return True

    def loadData(self):
        existed = self.getDataDir()
        if not existed:
            self.notificationsHistory = []
            self.statusHistory = []
            if self.dataDir is None:
                #no data dir, create message!
                return

        if QtCore.QFile(self.notificationsHistoryPath).exists():
            try:
                with open(self.notificationsHistoryPath, 'rb') as cachefile:
                    self.notificationsHistory = pickle.load(cachefile)
                    if not isinstance(self.notificationsHistory, list):
                        self.notificationsHistory = []
            except Exception as e:
                print 'error with cache loading: {}'.format(e)
                self.notificationsHistory = []
        else:
            try:
                self.notificationsHistory = []
                with open(self.notificationsHistoryPath, 'wb') as cachefile:
                    pickle.dump(self.notificationsHistory, cachefile)
            except Exception as e:
                print 'error writing cache data: {}'.format(e)

        if QtCore.QFile(self.statusPath).exists():
            try:
                with open(self.statusPath, 'rb') as cachefile:
                    self.statusHistory = pickle.load(cachefile)
                    if not isinstance(self.statusHistory, list):
                        self.statusHistory = []
            except Exception as e:
                print 'error with status loading: {}'.format(e)
                self.statusHistory = []
        else:
            try:
                self.statusHistory = []
                with open(self.statusPath, 'wb') as cachefile:
                    pickle.dump(self.statusHistory, cachefile)
            except Exception as e:
                print 'error writing status data: {}'.format(e)

    def updateStatus(self, *args):
        if self.phone.battery <= 1:
            return
        now = QtCore.QDateTime.currentMSecsSinceEpoch() / 1000
        if self.statusHistory:
            latest = self.statusHistory[-1]
            if self.phone.reachable:
                if self.settings.value('notifyChargeChanged', True).toBool() and \
                    latest.charging != self.phone.charging and \
                    abs(latest.time - now) > 5:
                        self.notifier.notify(icon='battery', title=self.phone.name, body='Charging' if self.phone.charging else 'Not charging!', priority=HIGH)
            if (latest.reachable, latest.battery, latest.charging) == (self.phone.reachable, self.phone.battery, self.phone.charging) and \
                abs(now - latest.time) < 30:
                    if self.phone.reachable:
                        self.computeBattery()
                    return
        self.statusHistory.append(StatusData(now, self.phone.reachable, self.phone.battery, self.phone.charging))
        if self.phone.reachable:
            self.computeBattery()
        self.getDataDir()
        if self.dataDir is None:
            return
        try:
            with open(self.statusPath, 'wb') as statusfile:
                pickle.dump(self.statusHistory, statusfile)
        except Exception as e:
            print 'error writing status: {}'.format(e)

    def clearNotificationsCache(self):
        self.notificationsHistory = []
        self.getDataDir()
        if self.dataDir is None:
            return
        try:
            with open(self.notificationsHistoryPath, 'wb') as cachefile:
                pickle.dump(self.notificationsHistory, cachefile)
        except Exception as e:
            print 'error writing cache: {}'.format(e)

    def clearStatusCache(self):
        self.statusHistory = []
        self.getDataDir()
        if self.dataDir is None:
            return
        try:
            with open(self.statusPath, 'wb') as statusfile:
                pickle.dump(self.statusHistory, statusfile)
        except Exception as e:
            print 'error writing status: {}'.format(e)

    def updateCache(self, notification):
        notification.time = QtCore.QDateTime.currentMSecsSinceEpoch() / 1000
        self.getDataDir()
        if self.dataDir is None:
            return
        def write():
            try:
                with open(self.notificationsHistoryPath, 'wb') as cachefile:
                    pickle.dump(self.notificationsHistory, cachefile)
            except Exception as e:
                print 'error writing cache: {}'.format(e)
        data = NotificationData(notification.time, notification.app, notification.ticker, notification.id)
        if not self.notificationsHistory or notification.id > self.notificationsHistory[-1].id:
            self.notificationsHistory.append(data)
#            print 'son quaaa {}'.format(notification.id)
            write()
            return
#        print ', '.join(tuple(str(n.id) for n in reversed(self.notificationsHistory[-20:])))
        for n in reversed(self.notificationsHistory[-20:]):
            if n.id == notification.id and n.app == notification.app and n.ticker == notification.ticker:
                break
            if n.id < notification.id:
                break
        else:
#            print 'son qui'
            self.notificationsHistory.append(data)
            write()
#        if (notification.id <= self.notificationsHistory[-1].id and self.notificationsHistory[-1].time > (time - 300)):
#        print self.notificationsHistory

    def computeBattery(self):
        if not self.statusHistory:
            return
        latest = self.statusHistory[-1]
        latestTime, latestReachable, latestBattery, latestCharging = latest
        statusRange = []
        latestAdded = False
        for status in reversed(self.statusHistory):
            if status == latest:
                statusRange.append(status)
                if latestAdded:
                    print 'something wrong computing battery?'
                else:
                    latestAdded = True
                continue
            if status.reachable is False:
                if abs(latest.time - status.time) > 300:
                    print 'a'
                    break
            if status.battery != latestBattery:
                if (latestCharging and status.battery > latestBattery) or (not latestCharging and status.battery < latestBattery):
                    print 'b'
                    print status.battery, latestCharging, latestBattery, latestTime, QtCore.QDateTime.currentMSecsSinceEpoch() / 1000
                    break
            if status.charging != latestCharging:
                if abs(latest.time - status.time) > 300:
                    print 'c'
                    break
            statusRange.append(status)
        else:
            print 'what?'
            return
        if not statusRange:
            return
        if len(statusRange) <= 1:
            self.setBatteryStats(None, None)
        else:
            if self.startUpTimer.elapsed() > 5:
                latestBattery = self.phone.battery
                previousBattery = statusRange[1].battery
                if latestBattery < previousBattery:
                    if self.settings.value('notifyBatteryDischargeAlert', True).toBool():
                        if latestBattery in self.notifyBatteryDischargeAlertIntervals:
                            self.notifier.notify(icon='battery-caution', title=self.phone.name, body='Battery low: {}%'.format(latestBattery))
                elif latestBattery < 100 and self.settings.value('notifyBatteryChargeAlert', True).toBool():
                    if latestBattery in self.notifyBatteryChargeAlertIntervals:
                        self.notifier.notify(icon='battery', title=self.phone.name, body='{}% of battery charge reached'.format(latestBattery))
            
            self.setBatteryStats(statusRange[-1], statusRange[0])

    def setChargeAlerts(self, group, key):
        if not group:
            if key == 'notifyBatteryChargeAlertIntervals':
                self.notifyBatteryChargeAlertIntervals = map(int, self.settings.value(key, settingsWidgets['notifyBatteryChargeAlertIntervals'].default).toPyObject().split(','))
            elif key == 'notifyBatteryDischargeAlertIntervals':
                self.notifyBatteryDischargeAlertIntervals = map(int, self.settings.value(key, settingsWidgets['notifyBatteryDischargeAlertIntervals'].default).toPyObject().split(','))

    def setBatteryStats(self, first, latest):
        if first is None or first.battery == latest.battery or first.time == latest.time:
            self.tooltipWidget.estimated = ''
            return
        if latest.battery <= 5 and not self.phone.charging:
            self.tooltipWidget.estimated = '!'
        time = abs(first.time - latest.time)
        diff = abs(first.battery - latest.battery)
        speed = float(diff) / time
        if self.phone.charging:
            if (latest.battery < first.battery):
                self.tooltipWidget.estimated = '?)'
            else:
                rem = int(divmod((100 - latest.battery) / speed, 60)[0])
                if rem <= 1:
                    rem = ''
                elif rem <= 60:
                    rem = ' ~{}m)'.format(rem)
                else:
                    rem = ' ~{}h {}m)'.format(*divmod(rem, 60))
                self.tooltipWidget.estimated = rem
        else:
            if (latest.battery > first.battery):
                self.tooltipWidget.estimated = '?'
            else:
                rem = int(divmod((latest.battery - 5) / speed, 60)[0])
                if rem <= 1:
                    rem = ''
                elif rem <= 60:
                    rem = ' (~{}m)'.format(rem)
                else:
                    rem = ' (~{}h {}m)'.format(*divmod(rem, 60))
                self.tooltipWidget.estimated = rem

    def createMenu(self):
        def showEvent(event):
            self.tooltipWidget.hide()
            self.tooltipWidget.mouseTimer.stop()
        self.menu = QtGui.QMenu()
        self.menu.setSeparatorsCollapsible(False)
        self.menu.showEvent = showEvent
        header = QtGui.QAction('KdeConnectTray', self.menu)
        header.setIcon(QtGui.QIcon('kdeconnect-tray-off.svg'))
        header.setSeparator(True)
        findMyPhoneAction = QtGui.QAction('Find my phone', self.menu)
        findMyPhoneAction.setIcon(QtGui.QIcon.fromTheme('edit-find'))
        findMyPhoneAction.triggered.connect(self.phone.findMyPhone)
        sep = QtGui.QAction(self.menu)
        sep.setSeparator(True)
        historyAction = QtGui.QAction('History...', self.menu)
        historyAction.setIcon(QtGui.QIcon.fromTheme('document-open-recent'))
        historyAction.triggered.connect(lambda: (showCenter(self.historyDialog), self.historyDialog.activateWindow()))
        settingsAction = QtGui.QAction('Settings...', self.menu)
        settingsAction.setIcon(QtGui.QIcon.fromTheme('preferences-system'))
        settingsAction.triggered.connect(self.showSettings)
        aboutSep = QtGui.QAction(self.menu)
        aboutSep.setSeparator(True)
        aboutAction = QtGui.QAction('About...', self.menu)
        aboutAction.setIcon(QtGui.QIcon.fromTheme('dialog-information'))
        aboutAction.triggered.connect(self.about)
        quitSep = QtGui.QAction(self.menu)
        quitSep.setSeparator(True)
        quitAction = QtGui.QAction('Quit', self.menu)
        quitAction.setIcon(QtGui.QIcon.fromTheme('application-exit'))
        quitAction.triggered.connect(self.quit)
        self.menu.addActions([header, findMyPhoneAction, sep, historyAction, settingsAction, aboutSep, aboutAction, quitSep, quitAction])
        self.setContextMenu(self.menu)
        self.phone.pluginsChanged.connect(
            lambda: findMyPhoneAction.setEnabled(
                True if self.phone.reachable and 'kdeconnect_findmyphone' in self.phone.loadedPlugins else False))
        #this connection is delayed since it might take a while for plugins to load once the device has become reachable
        self.phone.reachableChanged.connect(
            lambda reachable: findMyPhoneAction.setEnabled(False) if not reachable else \
                QtCore.QTimer.singleShot(2000, 
                lambda: findMyPhoneAction.setEnabled(
                    True if reachable and 'kdeconnect_findmyphone' in self.phone.loadedPlugins else False)))

    def about(self):
        def keyPressEvent(event):
            if event.key() == QtCore.Qt.Key_Escape:
                msgBox.accept()
        msgBox = QtGui.QMessageBox(
            QtGui.QMessageBox.Information, 
            'About KdeConnectTray', 
            '<h1>KdeConnectTray</h1>' \
            'version {version}<br/>' \
            'by Maurizio Berti'.format(version=VERSION)
            )
        msgBox.keyPressEvent = keyPressEvent
        btn = QtGui.QPushButton('About Qt...')
        btn.setIcon(QtGui.QIcon(':/trolltech/qmessagebox/images/qtlogo-64.png'))
        msgBox.addButton(btn, msgBox.ActionRole)
        btn.clicked.disconnect()
        btn.clicked.connect(lambda: QtGui.QMessageBox.aboutQt(msgBox))
        showCenter(msgBox)
        msgBox.exec_()

    def quit(self):
        self.notifier.quit()
#        self.notifierThread.quit()
        self.parent().quit()

    def showSettings(self):
        showCenter(self.settingsDialog)
        res = self.settingsDialog.exec_()
        print res

    def eventFilter(self, source, event):
        if event.type() == QtCore.QEvent.ToolTip:
            if self.phone.reachable:
                self.tooltipWidget.setSysTrayIconGeometry(self.geometry())
                self.tooltipWidget.show()
            return True
        return QtGui.QSystemTrayIcon.eventFilter(self, source, event)

    def show(self):
        QtGui.QSystemTrayIcon.show(self)
        QtCore.QTimer.singleShot(100, lambda: [self.activate(), self.updatePhone()])

    def activate(self):
        try:
#            self.phoneProxy = self.dbus.get_object('org.kde.kdeconnect', '/modules/kdeconnect/devices/{}'.format(self.phone.id))
            self.phone.setProxy(self.dbus)
#            self.phone.setReachable(self.phoneProps.Get('org.kde.kdeconnect.device', 'isReachable'))
#            self.phoneCmd = dbus.Interface(self.phoneProxy, dbus_interface='org.kde.kdeconnect.device')
#            print self.phoneProps.GetAll('org.kde.kdeconnect.device')
            return True
        except Exception as e:
            print 'Exception: {}'.format(e)
#            self.phoneProxy = None
#            self.phoneProps = None
#            self.phoneCmd = None

    @property
    def currentIcon(self):
        return self._currentIcon

    @currentIcon.setter
    def currentIcon(self, valid):
        if not valid:
            self._currentIcon = self.iconOff
            self.iconBlinkTimer.stop()
            QtGui.QSystemTrayIcon.setIcon(self, self._currentIcon)
        else:
            self._currentIcon = self.iconOn.getIcon(self.geometry())
            QtGui.QSystemTrayIcon.setIcon(self, self._currentIcon)
            self.iconBlinkTimer.start()

    def reachableChanged(self, state):
        if not state:
            self.setToolTip('No reachable phone.')
            self.currentIcon = False
            self.updateStatus()
            if self.settings.value('notifyUnreachable', True).toBool():
                self.notifier.notify(title=self.phone.name, body='Device is not reachable', icon=False)
            return
        self.setToolTip('')
        self.updatePhone()
        if self.settings.value('notifyReachable', True).toBool():
            self.notifier.notify(title=self.phone.name, body='Device is reachable')
#        battery is updated *after* reachable signal is sent, so we wait for it
        battery = self.phone.battery
        if battery <= 1:
            return
        QtCore.QTimer.singleShot(50, self.phone.refreshBattery)

    def updatePhone(self, *args):
        if not self.phone.reachable:
            return
        self.currentIcon = True
        self.tooltipWidget.updatePhone()
        if not self.phone.notifications:
            self.tooltipWidget.spacer.setVisible(False)
        return

    def setCurrentIcon(self, state):
        if self.settings.value('lowBatteryIconBlink', settingsWidgets['lowBatteryIconBlink'].default).toBool():
            if self.phone.battery > self.settings.value('lowBatteryIconBlinkValue', settingsWidgets['lowBatteryIconBlinkValue'].default).toPyObject():
                self.iconBlinkTimer.stop()
                state = True
        else:
            self.iconBlinkTimer.stop()
            state= True
        QtGui.QSystemTrayIcon.setIcon(self, self._currentIcon if state else QtGui.QIcon())

    def owner_changed(self, name, old, new):
        print name
        if str(name) == 'org.kde.kdeconnect':
            if len(new):
                self.spotify_active(self.spotify_connect())
            else:
                self.spotify_active(False)


class DeviceDialog(QtGui.QDialog):
    def __init__(self, currentID, parent=None, alert=False):
        QtGui.QDialog.__init__(self, parent)
        self.setWindowTitle('Select a remote device')
        self.currentID = currentID
        self.currentDeviceIndex = None

        devProxy = dbus.SessionBus().get_object('org.kde.kdeconnect', '/modules/kdeconnect')
        self.daemonIface = dbus.Interface(devProxy, dbus_interface='org.kde.kdeconnect.daemon')
        self.daemonIface.connect_to_signal('deviceVisibilityChanged', self.deviceVisibilityChanged)
        self.daemonIface.connect_to_signal('deviceAdded', lambda dev: self.deviceVisibilityChanged(dev, True))
        self.daemonIface.connect_to_signal('deviceRemoved', lambda dev: self.deviceVisibilityChanged(dev, False))
        self.propsIface = dbus.Interface(devProxy, dbus_interface='org.freedesktop.DBus.Properties')

        layout = QtGui.QGridLayout()
        self.setLayout(layout)
        layout.addWidget(QtGui.QLabel('Please select a device:'))
        self.deviceTable = QtGui.QTableView()
        layout.addWidget(self.deviceTable)

        if alert:
            layout.addWidget(QtGui.QLabel(
                'Device change requires a restart.<br/>Clicking "Ok" with a different selected device will close the program.'
                ))

        self.buttonBox = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok|QtGui.QDialogButtonBox.Cancel)
        self.OkBtn = self.buttonBox.button(self.buttonBox.Ok)
        self.OkBtn.setEnabled(False)
        self.OkBtn.clicked.connect(self.accept)
        self.buttonBox.button(self.buttonBox.Cancel).clicked.connect(self.reject)
        self.pairBtn = QtGui.QPushButton('Pair')
        self.pairBtn.setEnabled(False)
        self.pairBtn.clicked.connect(self.requestPair)
        self.buttonBox.addButton(self.pairBtn, self.buttonBox.ActionRole)
        layout.addWidget(self.buttonBox)

        self.deviceModel = QtGui.QStandardItemModel()
        self.deviceModel.setHorizontalHeaderLabels(['ID', 'Name', 'Paired'])
        self.deviceTable.setModel(self.deviceModel)
        self.deviceTable.horizontalHeader().setHighlightSections(False)
        self.deviceTable.setSelectionMode(self.deviceTable.SingleSelection)
        self.deviceTable.setSelectionBehavior(self.deviceTable.SelectRows)
        self.deviceTable.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.deviceTable.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.deviceTable.setItemDelegateForColumn(2, CheckBoxDelegate())
        self.deviceTable.setEditTriggers(self.deviceTable.NoEditTriggers)
        self.deviceTable.verticalHeader().setVisible(False)
        self.deviceTable.activated.connect(self.checkPairing)
        self.deviceTable.clicked.connect(self.checkPairing)
        self.deviceTable.pressed.connect(self.checkPairing)

        for devID in self.daemonIface.devices():
            devProxy = dbus.SessionBus().get_object('org.kde.kdeconnect', '/modules/kdeconnect/devices/' + devID)
            devIface = dbus.Interface(devProxy, dbus_interface='org.freedesktop.DBus.Properties')
            devItem = QtGui.QStandardItem(devID)
            devType = unicode(devIface.Get('org.kde.kdeconnect.device', 'type'))
            devItem.setIcon(QtGui.QIcon.fromTheme('computer-laptop' if devType == 'laptop' else devType))
            nameItem = QtGui.QStandardItem(devIface.Get('org.kde.kdeconnect.device', 'name'))
            pairedItem = QtGui.QStandardItem()
            paired = bool(devIface.Get('org.kde.kdeconnect.device', 'isTrusted'))
            pairedItem.setData(paired, QtCore.Qt.CheckStateRole)
            dbus.Interface(devProxy, dbus_interface='org.kde.kdeconnect.device').connect_to_signal(
                'trustedChanged', 
                lambda paired, pairedItem=pairedItem: pairedItem.setData(bool(paired), QtCore.Qt.CheckStateRole))
            if not bool(devIface.Get('org.kde.kdeconnect.device', 'isReachable')):
                pairedItem.setEnabled(False)
            self.deviceModel.appendRow([devItem, nameItem, pairedItem])
            if devID == currentID:
                self.currentDeviceIndex = devItem.index()
                setBold(devItem)
                setBold(nameItem)
                self.deviceTable.setCurrentIndex(self.currentDeviceIndex)
                if paired:
                    self.OkBtn.setEnabled(True)
                else:
                    self.pairBtn.setEnabled(True)

        if not self.deviceModel.rowCount():
            blankItem = QtGui.QStandardItem('No device available')
            blankItem.setEnabled(False)
            setItalic(blankItem)
            blankItem.setData(QtCore.Qt.lightGray, QtCore.Qt.ForegroundRole)
            self.deviceModel.appendRow(blankItem)
            self.deviceTable.setSpan(0, 0, 1, 3)

        self.deviceModel.dataChanged.connect(self.deviceModelChanged)
        self.deviceTable.resizeColumnsToContents()
        minHeight = self.deviceTable.verticalHeader().length() if self.deviceModel.rowCount() else self.deviceTable.verticalHeader().defaultSectionSize()
        self.deviceTable.setMaximumHeight(minHeight + self.deviceTable.frameWidth() * 2 + self.deviceTable.horizontalHeader().height())

    def exec_(self):
        res = QtGui.QDialog.exec_(self)
        if not res:
            return res
        devID = unicode(self.deviceTable.currentIndex().sibling(self.deviceTable.currentIndex().row(), 0).data().toPyObject())
        devProxy = dbus.SessionBus().get_object('org.kde.kdeconnect', '/modules/kdeconnect/devices/' + devID)
        devIface = dbus.Interface(devProxy, dbus_interface='org.kde.kdeconnect.device')
        loadedPlugins = set(map(unicode, devIface.loadedPlugins()))
        if not KdeConnectRequiredPlugins & loadedPlugins:
            missingPlugins = KdeConnectRequiredPlugins & loadedPlugins ^ KdeConnectRequiredPlugins
            settings = QtCore.QSettings(devIface.pluginsConfigFile(), QtCore.QSettings.NativeFormat)
            settings.beginGroup('plugins')
            for missing in missingPlugins:
                settings.setValue('{}Enabled'.format(missing), True)
            settings.endGroup()
            settings.sync()
            devIface.reloadPlugins()
        return devID

    def deviceModelChanged(self, index, _):
        if index.column() == 2:
            paired = index.data(QtCore.Qt.CheckStateRole).toBool()
            if index.row() == self.deviceTable.currentIndex().row():
                self.OkBtn.setEnabled(paired)
                self.pairBtn.setEnabled(not paired)

    def showEvent(self, event=None):
        self.deviceTable.horizontalHeader().setResizeMode(0, QtGui.QHeaderView.Stretch)
        self.deviceTable.horizontalHeader().setResizeMode(1, QtGui.QHeaderView.Stretch)
        self.deviceTable.horizontalHeader().setResizeMode(2, QtGui.QHeaderView.Fixed)
        self.deviceTable.setMinimumWidth(self.deviceTable.horizontalHeader().length() + self.deviceTable.frameWidth() * 2)

    def requestPair(self):
        devItem = self.deviceModel.itemFromIndex(self.deviceTable.currentIndex().sibling(self.deviceTable.currentIndex().row(), 0))
        dev = unicode(devItem.text())
        devProxy = dbus.SessionBus().get_object('org.kde.kdeconnect', '/modules/kdeconnect/devices/' + dev)
        devIface = dbus.Interface(devProxy, dbus_interface='org.kde.kdeconnect.device')
        devIface.requestPair()

    def deviceVisibilityChanged(self, dev, state):
        #dev is a dbus.String type, we need to convert it
        dev = unicode(dev)
        matches = self.deviceModel.match(self.deviceModel.index(0, 0), QtCore.Qt.DisplayRole, dev, -1, QtCore.Qt.MatchExactly|QtCore.Qt.MatchWrap)
        if state and not matches:
            self.deviceModel.blockSignals(True)
            if self.deviceTable.columnSpan(0, 0) > 1:
                self.deviceModel.takeRow(0)
                self.deviceTable.setSpan(0, 0, 1, 1)
            devProxy = dbus.SessionBus().get_object('org.kde.kdeconnect', '/modules/kdeconnect/devices/' + dev)
#            devIface = dbus.Interface(devProxy, dbus_interface='org.kde.kdeconnect.device')
            propsIface = dbus.Interface(devProxy, dbus_interface='org.freedesktop.DBus.Properties')
            devItem = QtGui.QStandardItem(dev)
            devType = propsIface.Get('org.kde.kdeconnect.device', 'type')
            devItem.setIcon(QtGui.QIcon.fromTheme('computer-laptop' if devType == 'laptop' else devType))
            nameItem = QtGui.QStandardItem(propsIface.Get('org.kde.kdeconnect.device', 'name'))
            pairedItem = QtGui.QStandardItem()
            pairedItem.setData(bool(propsIface.Get('org.kde.kdeconnect.device', 'isTrusted')), QtCore.Qt.CheckStateRole)
            dbus.Interface(devProxy, dbus_interface='org.kde.kdeconnect.device').connect_to_signal(
                'trustedChanged', 
                lambda paired, pairedItem=pairedItem: pairedItem.setData(bool(paired), QtCore.Qt.CheckStateRole))
            self.deviceModel.appendRow([devItem, nameItem, pairedItem])
            self.deviceTable.resizeColumnsToContents()
            self.deviceTable.setMaximumHeight(self.deviceTable.verticalHeader().length() + self.deviceTable.frameWidth() * 2 + self.deviceTable.horizontalHeader().height())
            self.deviceModel.blockSignals(False)
        if not matches:
            return
        if self.deviceModel.rowCount() == 1:
            self.deviceTable.setCurrentIndex(self.deviceModel.index(0, 0))
        if len(matches) > 1:
            print 'Something is wrong: multiple matches!'
        refIndex = matches[0]
        if refIndex.row() == self.deviceTable.currentIndex().row():
            devItem = self.deviceModel.itemFromIndex(refIndex.sibling(refIndex.row(), 0))
            nameItem = self.deviceModel.itemFromIndex(refIndex.sibling(refIndex.row(), 1))
            pairedItem = self.deviceModel.itemFromIndex(refIndex.sibling(refIndex.row(), 2))
            paired = pairedItem.data(QtCore.Qt.CheckStateRole).toBool()
            if paired:
                devItem.setEnabled(True)
                nameItem.setEnabled(True)
                pairedItem.setEnabled(True if state else False)
                self.pairBtn.setEnabled(False)
                self.OkBtn.setEnabled(True)
            else:
                devItem.setEnabled(state)
                nameItem.setEnabled(state)
                pairedItem.setEnabled(state)
                self.pairBtn.setEnabled(True if state else False)
                self.OkBtn.setEnabled(False)

    def checkPairing(self, index):
        if not index.isValid():
            self.pairBtn.setEnabled(False)
            return
        if not self.deviceModel.itemFromIndex(index).isEnabled():
            self.pairBtn.setEnabled(False)
            self.OkBtn.setEnabled(False)
            return
        paired = index.sibling(index.row(), 2).data(QtCore.Qt.CheckStateRole).toBool()
        if paired:
            self.pairBtn.setEnabled(False)
            self.OkBtn.setEnabled(True)
        else:
            self.pairBtn.setEnabled(True)
            self.OkBtn.setEnabled(False)


def main():
    app = QtGui.QApplication(sys.argv)
    app.setOrganizationName('jidesk')
    app.setApplicationName('KdeConnectTray')
    app.setQuitOnLastWindowClosed(False)
    DBusQtMainLoop(set_as_default=True)
    currentID = unicode(QtCore.QSettings().value('deviceID', None).toPyObject())
    currentPaired = False
    if currentID:
        try:
            baseProxy = dbus.SessionBus().get_object('org.kde.kdeconnect', '/modules/kdeconnect')
            baseIface = dbus.Interface(baseProxy, dbus_interface='org.kde.kdeconnect.daemon')
            if currentID in baseIface.devices():
                devProxy = dbus.SessionBus().get_object('org.kde.kdeconnect', '/modules/kdeconnect/devices/' + currentID)
                devIface = dbus.Interface(devProxy, dbus_interface='org.kde.kdeconnect.device')
                if not devIface.isTrusted():
                    raise
                currentPaired = True
        except:
            msgBox = QtGui.QMessageBox(QtGui.QMessageBox.Warning, 
                'Previously used device not found', 
                'The previously used device has not been found!<br/><br/>' \
                'Before proceeding, please check that:<br/>' \
                '- <a href="https://play.google.com/store/apps/details?id=org.kde.kdeconnect_tp" title="App page on Google Play">KdeConnect app</a> ' \
                '(link on Google Play) is installed on the device.<br/>' \
                '- The device is connected to the same network as this computer is.<br/><br/>' \
                'If the problem still occurs, contact me.')
            showCenter(msgBox)
            msgBox.exec_()
    if not currentPaired:
        deviceDialog = DeviceDialog(currentID)
        showCenter(deviceDialog)
        currentID = deviceDialog.exec_()
        if not currentID:
            app.quit()
            quit()
#        currentID = deviceDialog.deviceTable.currentIndex().sibling(deviceDialog.deviceTable.currentIndex().row(), 0).data().toPyObject()
    trayicon = KdeConnect(app, currentID)
    trayicon.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
