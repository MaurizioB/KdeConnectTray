#!/usr/bin/env python2.7
# *-* coding: utf-8 *-*

import os
from PyQt4 import QtCore, QtGui, uic

#basePath = os.path.dirname(os.path.abspath(__file__))
basePath = os.path.abspath(os.path.join(__file__, os.pardir, os.pardir))
defaultIconsPath = os.path.join(basePath, 'icons')

def loadUi(uiFileName, widget):
    return uic.loadUi(os.path.join(basePath, 'dialogs', uiFileName), widget)

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

def menuSeparator(parent=None, caption=''):
    sep = QtGui.QAction(caption, parent) if caption else QtGui.QAction(parent)
    sep.setSeparator(True)
    return sep

def simpleTimeFormat(time):
    if isinstance(time, float):
        time = int(round(time))
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
