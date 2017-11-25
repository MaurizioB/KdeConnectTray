#!/usr/bin/env python2.7
# *-* coding: utf-8 *-*

from PyQt4 import QtCore, QtGui
from src.classes import *
from src.constants import *

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
                ticker=re.sub(urlRegex, lambda m: u''.join(u' <a href="{t}">{t}</a>'.format(t=t) for t in m.groups()), self.notification.ticker), 
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
        elif iconName:
            return u'<img src="{}/{}.png"> '.format(self.main.iconsPath, self.app)
        elif self.app in self.main.defaultIcons:
            return u'<img src="{}/{}.png"> '.format(defaultIconsPath, self.app)
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
                charging = ' (charging{})'.format(self.estimated)
        else:
            charging = self.estimated
        self.batteryLabel.setText('<font color="#{color}">{battery}%</font>{charging}'.format(
            color='{:02x}{:02x}{:02x}'.format(*map(int, batteryColor(self.phone.battery))), 
            battery=self.phone.battery, 
#            charging=' (charging{})'.format(self.estimated) if self.phone.charging else self.estimated
            charging=charging
            ))
        showUndismissable = self.settings.value('showUndismissable', settingsWidgets['showUndismissable'].default).toBool()
        ignored = self.settings.value('ignoredApps', []).toPyObject()
        try:
            ignored.split(',')
        except:
            pass
        delete = set()
        hidden = []
        undismissable = []
        normal = []
        for id in sorted(self.phone.notifications.keys()):
            n = self.phone.notifications[id]
            if n.app in ignored:
                hidden.append(n)
            if not n.dismissable:
                undismissable.append(n)
            else:
                normal.append(n)

        visible = set(normal + (undismissable if showUndismissable else [])) ^ set(hidden)
#        self.spacer.setVisible(True if (undismissable + normal and showUndismissable) or normal else False)
        self.spacer.setVisible(True if visible else False)

        for n in undismissable + normal:
            if n in self.notifications:
                if n in hidden:
                    delete.add(n)
                elif not n.dismissable and not showUndismissable:
                    delete.add(n)
                continue
            if n in hidden:
                if n in self.notifications:
                    delete.add(n)
                continue
            label = NotificationLabel(self.main, n)
            btn = QtGui.QPushButton()
            label.hideAllNotifications.connect(lambda: [self.dismissNotification(n) for n in self.notifications.keys()])
            if n.dismissable:
                label.hideNotification.connect(self.dismissNotification)
                btn.setIcon(self.style().standardIcon(QtGui.QStyle.SP_DialogCloseButton))
                btn.setStyleSheet('background-color: rgba(50, 50, 50, 100);')
                btn.setMaximumSize(22, 22)
                btn.clicked.connect(lambda state, n=n: self.dismissNotification(n))
                self.notificationLayout.addWidget(label)
                self.notificationLayout.addWidget(btn, self.notificationLayout.rowCount() - 1, 1)
            elif showUndismissable:
                self.notificationLayout.addWidget(label, self.notificationLayout.rowCount(), 0, 1, 2)
            self.notifications[n] = label, btn
        for n in self.notifications:
            if not n in self.phone.notifications.values():
                delete.add(n)
        if not delete:
            self.adjustSize()
            return
        for n in delete:
            try:
                label, btn = self.notifications.pop(n)
                self.notificationLayout.removeWidget(label)
                label.deleteLater()
                self.notificationLayout.removeWidget(btn)
                btn.deleteLater()
            except:
                pass
            try:
                #might have been already removed
                n.deleteLater()
            except:
                pass
        self.adjustSize()
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
        self.adjustSize()
        if self.iconRect.y() < 100:
            #sopra
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
        self.dynResize()
        desktop = QtGui.QApplication.desktop()
        x = self.iconRect.x()
        y = self.iconRect.y()
        if x + self.width() > desktop.width():
            x = desktop.width() - self.width() - 4
        elif x < 0:
            x = 4
        if y > 10:
            y = self.iconRect.y() - self.height() - 4
        else:
            y += self.iconRect.height() + 4
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


