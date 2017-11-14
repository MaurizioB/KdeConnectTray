#!/usr/bin/env python2.7
# *-* coding: utf-8 *-*

import sys
import dbus
import pickle
import os
from glob import glob
from PyQt4 import QtGui, QtCore
from dbus.mainloop.qt import DBusQtMainLoop

from src.info import __version__
from src.constants import *
from src.utils import *
from src.dialogs import *
from src.classes import *
from src.widgets import *



class KdeConnect(QtGui.QSystemTrayIcon):
    def __init__(self, parent, deviceID):
        self.iconOff = QtGui.QIcon('{}/kdeconnect-tray-off.svg'.format(iconsPath))
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
        for _iconPath in glob('{}/*'.format(iconsPath)):
                _iconName = os.path.basename(_iconPath)
                self.defaultIcons[_iconName[:-4]] = QtGui.QIcon(_iconPath)
        self.notifierThread.start()
        self.notifier.notify(body='Started!')
        QtCore.QTimer.singleShot(1000, self.missingRequiredPluginDialog.updatePlugins)
        self.iconBlinkTimer = DualTimer(self)
        self.iconBlinkTimer.setIntervals(250, 750)
        self.iconBlinkTimer.timeoutDual.connect(self.setCurrentIcon)
        self._currentIcon = self.iconOff

#        self.fd_iface.connect_to_signal('NameOwnerChanged', self.owner_changed)

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
        header.setIcon(QtGui.QIcon('{}/kdeconnect-tray-off.svg'.format(iconsPath)))
        header.setSeparator(True)
        self.menu.addAction(header)

        utilsMenu = QtGui.QMenu('Utilities')
        utilsMenu.setIcon(QtGui.QIcon.fromTheme('applications-utilities'))
        self.menu.addMenu(utilsMenu)
        findMyPhoneAction = QtGui.QAction('Find my phone', self.menu)
        findMyPhoneAction.setIcon(QtGui.QIcon.fromTheme('edit-find'))
        findMyPhoneAction.triggered.connect(self.phone.findMyPhone)
        findMyPhoneAction.setEnabled(True if self.phone.hasPlugin('kdeconnect_findmyphone') else False)
        sendFileAction = QtGui.QAction('Send file...', self.menu)
        sendFileAction.setIcon(QtGui.QIcon.fromTheme('mail-attachment'))
        sendFileAction.triggered.connect(self.sendFile)
        sendFileAction.setEnabled(True if self.phone.hasPlugin('kdeconnect_share') else False)
        utilsMenu.setEnabled(True if self.phone.reachable and (findMyPhoneAction.isEnabled() or sendFileAction.isEnabled()) else False)
        utilsMenu.addActions([findMyPhoneAction, sendFileAction])

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
        aboutAction.setIcon(QtGui.QIcon.fromTheme('help-about'))
        aboutAction.triggered.connect(self.about)
        quitSep = QtGui.QAction(self.menu)
        quitSep.setSeparator(True)
        quitAction = QtGui.QAction('Quit', self.menu)
        quitAction.setIcon(QtGui.QIcon.fromTheme('application-exit'))
        quitAction.triggered.connect(self.quit)
        self.menu.addActions([sep, historyAction, settingsAction, aboutSep, aboutAction, quitSep, quitAction])
        self.setContextMenu(self.menu)
        self.phone.pluginsChanged.connect(
            lambda: (findMyPhoneAction.setEnabled(
                True if self.phone.reachable and self.phone.hasPlugin('kdeconnect_findmyphone') else False), 
                    sendFileAction.setEnabled(
                True if self.phone.reachable and self.phone.hasPlugin('kdeconnect_share') else False), 
                    utilsMenu.setEnabled(True if self.phone.reachable and (findMyPhoneAction.isEnabled() or sendFileAction.isEnabled()) else False)
                ))

        self.phone.reachableChanged.connect(
            lambda reachable: utilsMenu.setEnabled(False) if not reachable else (
                findMyPhoneAction.setEnabled(True if self.phone.hasPlugin('kdeconnect_findmyphone') else False), 
                sendFileAction.setEnabled(True if self.phone.hasPlugin('kdeconnect_share') else False), 
                utilsMenu.setEnabled(True if self.phone.reachable and (findMyPhoneAction.isEnabled() or sendFileAction.isEnabled()) else False)
                ))

    def sendFile(self):
        fileName = QtGui.QFileDialog.getOpenFileName(None, 
            u'Select the file to send to the device', 
            os.path.expanduser('~')
            )
        if not fileName:
            return
        self.phone.share(fileName)

    def about(self):
        def keyPressEvent(event):
            if event.key() == QtCore.Qt.Key_Escape:
                msgBox.accept()
        msgBox = QtGui.QMessageBox(
            QtGui.QMessageBox.Information, 
            'About KdeConnectTray', 
            '<h1>KdeConnectTray</h1>' \
            'version {version}<br/>' \
            'by Maurizio Berti'.format(version=__version__)
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
        self.settingsDialog.exec_()

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
            self.phone.setProxy(self.dbus)
            self.createMenu()
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
        if self.phone.charging:
            self.iconBlinkTimer.stop()
            state= True
        elif self.settings.value('lowBatteryIconBlink', settingsWidgets['lowBatteryIconBlink'].default).toBool():
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
    trayicon = KdeConnect(app, currentID)
    trayicon.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
