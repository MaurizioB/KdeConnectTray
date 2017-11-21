#!/usr/bin/env python2.7
# *-* coding: utf-8 *-*

import dbus
import gettext
import uuid
import json
from PyQt4 import QtCore, QtGui
from src.utils import *
from src.constants import *
from src.classes import *


class BasePluginDialog(QtGui.QDialog):
    def __init__(self, parent, config):
        QtGui.QDialog.__init__(self, parent)
        self.layout = QtGui.QVBoxLayout()
        self.setLayout(self.layout)
        self.contentLayout = QtGui.QGridLayout()
        self.buttonBox = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok|QtGui.QDialogButtonBox.Cancel|QtGui.QDialogButtonBox.RestoreDefaults)
        self.restoreBtn = self.buttonBox.button(self.buttonBox.RestoreDefaults)
        self.restoreBtn.setIcon(QtGui.QIcon.fromTheme('edit-undo'))
        self.okBtn = self.buttonBox.button(self.buttonBox.Ok)
        self.okBtn.clicked.connect(self.apply)
        self.buttonBox.button(self.buttonBox.Cancel).clicked.connect(self.reject)
        self.layout.addLayout(self.contentLayout)
        self.layout.addWidget(self.buttonBox)
        self.settings = QtCore.QSettings(config, QtCore.QSettings.NativeFormat)


#class PluginSendNotifications(BasePluginDialog):
#    def __init__(self, parent, config):
#        BasePluginDialog.__init__(self, parent, config)
#        t = gettext.translation('kdeconnect-plugins', '/usr/share/locale', fallback=True)
#        _ = t.ugettext
#        self.setWindowTitle(_('Send notifications'))
#        self.settings.beginGroup('applications')
#        for k in self.settings.allKeys():
#            v = self.settings.value(k, type=QtCore.QMetaType)
#            qv = QtCore.QVariant()
#            v >> qv
#            print qv.isNull()
##            print dir(v)
##            print v.type()
#        print [k for k in self.settings.allKeys()]
##        for appValue in self.settings.childGroups():
##            print appValue
##            print [k for k in self.settings.childKeys()]
###            print self.settings.value(appValue).toPyObject()
##            print self.settings.value('{}/value'.format(appValue))
##            print self.settings.value('size').toPyObject()
##        print [v for v in self.settings.childGroups()]
#        self.settings.endGroup()
#
#    def apply(self):
#        pass


class CmdItemDelegate(QtGui.QStyledItemDelegate):
    clicked = QtCore.pyqtSignal(object)

    def paint(self, painter, style, index):
        QtGui.QStyledItemDelegate.paint(self, painter, style, index)
        rect = style.rect
        btn = QtGui.QStyleOptionButton()
        btn.rect = QtCore.QRect(rect.left() + rect.width() - 30, rect.top(), 30, 30)
        btn.icon = QtGui.QIcon.fromTheme('document-open')
        btn.state = QtGui.QStyle.State_Enabled
        QtGui.QApplication.style().drawControl(QtGui.QStyle.CE_PushButton, btn, painter)

    def editorEvent(self, event, model, style, index):
        if event.type() == QtCore.QEvent.MouseButtonPress:
            rect = style.rect
            btnRect = QtCore.QRect(rect.left() + rect.width() - 30, rect.top(), 30, 30)
            if event.pos() in btnRect:
                self.clicked.emit(index)
                return True
        return QtGui.QStyledItemDelegate.editorEvent(self, event, model, style, index)


class PluginRunCommands(BasePluginDialog):
    def __init__(self, parent, config):
        BasePluginDialog.__init__(self, parent, config)
        t = gettext.translation('kdeconnect-plugins', '/usr/share/locale', fallback=True)
        _ = t.ugettext
        self.setWindowTitle(_('Run commands'))
        layout = self.contentLayout
        self.cmdModel = QtGui.QStandardItemModel()
        self.cmdTable = QtGui.QTableView()
        cmdItemDelegate = CmdItemDelegate()
        cmdItemDelegate.clicked.connect(self.browse)
        self.cmdTable.setItemDelegateForColumn(1, cmdItemDelegate)
        self.cmdTable.setMouseTracking(True)
        self.cmdTable.setModel(self.cmdModel)
        layout.addWidget(self.cmdTable, 0, 0, 3, 1)
        self.cmdTable.verticalHeader().setVisible(False)
        self.resetModel()
#        count = 0
        for id, cmdDict in json.loads(unicode(self.settings.value('commands').toString())).items():
            name = cmdDict['name']
            cmd = cmdDict['command']
            nameItem = QtGui.QStandardItem(name)
            nameItem.setData(id.strip('{}'))
            cmdItem = QtGui.QStandardItem(cmd)
#            browseItem = QtGui.QStandardItem()
            self.cmdModel.appendRow([nameItem, cmdItem])

#            browseBtn = QtGui.QPushButton(self)
#            browseBtn.setIcon(QtGui.QIcon.fromTheme('document-open'))
#            browseBtn.clicked.connect(lambda state, browseItem=browseItem: self.browse(browseItem))
#            self.cmdTable.setIndexWidget(self.cmdModel.index(self.cmdModel.rowCount() - 1, 2), browseBtn)
#            count += 1
        self.addEmptyCmdItem()
        self.cmdTable.resizeColumnToContents(0)
        self.cmdTable.resizeColumnToContents(2)
        self.cmdTable.horizontalHeader().setResizeMode(1, QtGui.QHeaderView.Stretch)
        self.cmdTable.horizontalHeader().setResizeMode(2, QtGui.QHeaderView.Fixed)

        self.addBtn = QtGui.QPushButton()
        self.addBtn.setIcon(QtGui.QIcon.fromTheme('list-add'))
        self.addBtn.setToolTip('Add new command')
        layout.addWidget(self.addBtn, 0, 1)
        self.delBtn = QtGui.QPushButton()
        self.delBtn.setIcon(QtGui.QIcon.fromTheme('list-remove'))
        self.delBtn.setToolTip('Delete selected command')
        self.delBtn.setEnabled(False)
        self.delBtn.clicked.connect(self.deleteCmd)
        layout.addWidget(self.delBtn, 1, 1)

        self.cmdModel.dataChanged.connect(self.updateCmds)
        self.cmdTable.selectionModel().currentChanged.connect(self.selectionChanged)
        self.restoreBtn.clicked.connect(self.resetModel)

    def browse(self, index):
        browseDialog = QtGui.QFileDialog(self, 'Select the command to execute', os.path.expanduser(u'~/{}'.format(index.data().toPyObject())))
        browseDialog.setFilter(QtCore.QDir.Executable)
        res = browseDialog.exec_()
        if not res:
            return
        self.cmdModel.itemFromIndex(index).setText(browseDialog.selectedFiles()[0])

    def deleteCmd(self):
        if not self.cmdTable.currentIndex().isValid():
            return
        column = self.cmdTable.currentIndex().column()
        row = self.cmdTable.currentIndex().row()
        self.cmdModel.takeRow(row)
        nameItem = self.cmdModel.item(row, 0)
        cmdItem = self.cmdModel.item(row, 1)
        if row == 0:
            index = self.cmdModel.index(0, column)
        elif nameItem.text() or cmdItem.text():
            index = self.cmdModel.index(row, column)
        else:
            index = self.cmdModel.index(row - 1, column)
        self.cmdTable.setCurrentIndex(index)

    def selectionChanged(self, index, previous):
        if index.data().toPyObject():
            self.delBtn.setEnabled(True)
            return
        sibling = index.sibling(index.row(), 0 if index.column() else 1)
        self.delBtn.setEnabled(True if sibling.data().toPyObject() else False)

    def updateCmds(self, index, _):
        self.cmdModel.dataChanged.disconnect()
        blankRows = []
        for row in xrange(self.cmdModel.rowCount()):
            nameItem = self.cmdModel.item(row, 0)
            cmdItem = self.cmdModel.item(row, 1)
            if not nameItem.text() and not cmdItem.text():
                if row <= self.cmdModel.rowCount() - 2:
                    blankRows.append(row)
                continue
            if not nameItem.text() or not cmdItem.text():
                self.okBtn.setEnabled(False)
                break
        else:
            self.okBtn.setEnabled(True)
        [self.cmdModel.takeRow(row) for row in reversed(blankRows)]
        if self.cmdModel.item(self.cmdModel.rowCount() - 1, 0).text() and self.cmdModel.item(self.cmdModel.rowCount() - 1, 1).text():
            prevRow = self.cmdModel.rowCount() - 1
            if self.cmdModel.item(prevRow, 0).text() and self.cmdModel.item(prevRow, 1).text():
                self.addEmptyCmdItem()
        column = index.column()
        if column == 0:
            nextIndex = self.cmdModel.index(index.row(), 1)
            self.cmdTable.setCurrentIndex(nextIndex)
        elif index.row() < self.cmdModel.rowCount() - 1:
            nextIndex = self.cmdModel.index(index.row() + 1, 0)
            self.cmdTable.setCurrentIndex(nextIndex)
        self.cmdModel.dataChanged.connect(self.updateCmds)

    def resetModel(self):
        t = gettext.translation('kdeconnect-plugins', '/usr/share/locale', fallback=True)
        _ = t.ugettext
        self.cmdModel.clear()
        self.cmdModel.setHorizontalHeaderLabels([_('Name'), _('Command'), ''])

    def addEmptyCmdItem(self):
        emptyNameItem = QtGui.QStandardItem()
        emptyNameItem.setData(unicode(uuid.uuid4()))
        self.cmdModel.appendRow([emptyNameItem, QtGui.QStandardItem()])

    def apply(self):
        cmdDict = {}
        for row in xrange(self.cmdModel.rowCount()):
            nameItem = self.cmdModel.item(row, 0)
            name = unicode(nameItem.text())
            cmdId = unicode(nameItem.data(QtCore.Qt.UserRole + 1).toPyObject())
            cmd = unicode(self.cmdModel.item(row, 1).text())
            if not (name and cmd):
                continue
            if not cmdId:
                cmdId = unicode(uuid.uuid4())
            cmdDict[cmdId] = {'command': cmd, 'name': name}
        self.settings.setValue('commands', json.dumps(cmdDict))
        self.settings.sync()
        self.accept()


class PluginShare(BasePluginDialog):
    defaults = {
        'incoming_path': os.path.expanduser('~/Downloads')
        }

    def __init__(self, parent, config):
        BasePluginDialog.__init__(self, parent, config)
        t = gettext.translation('kdeconnect-plugins', '/usr/share/locale', fallback=True)
        _ = t.ugettext
        self.setWindowTitle(_('Share and receive'))
        groupBox = QtGui.QGroupBox()
        self.contentLayout.addWidget(groupBox)
        layout = QtGui.QGridLayout()
        groupBox.setLayout(layout)
        editLbl = QtGui.QLabel(_('Save files in:'))
        layout.addWidget(editLbl)
        self.folderEdit = QtGui.QLineEdit(self.settings.value('incoming_path', self.defaults['incoming_path']).toString())
        layout.addWidget(self.folderEdit, 0, 1)
        browseBtn = QtGui.QPushButton()
        browseBtn.setIcon(QtGui.QIcon.fromTheme('document-open'))
        browseBtn.clicked.connect(self.browse)
        layout.addWidget(browseBtn, 0, 2)
        footerLbl = QtGui.QLabel(_('&percnt;1 in the path will be replaced with the specific device name.'))
        footerLbl.setTextFormat(QtCore.Qt.RichText)
        layout.addWidget(footerLbl, 1, 0, 1, 3)
        self.restoreBtn.clicked.connect(lambda:
            self.folderEdit.setText(self.defaults['incoming_path'])
            )

    def browse(self):
        dirName = QtGui.QFileDialog.getExistingDirectory(self, 
            u'Select folder for download',  
            os.path.expanduser('~')
            )
        if not dirName:
            return
        self.folderEdit.setText(dirName)

    def apply(self):
        self.settings.setValue('incoming_path', self.folderEdit.text())
        self.settings.sync()
        self.accept()


class PluginPauseMusic(BasePluginDialog):
    defaults = {
        'actionMute': False, 
        'actionPause': True, 
        'conditionTalking': False, 
        }
    def __init__(self, parent, config):
        BasePluginDialog.__init__(self, parent, config)
        t = gettext.translation('kdeconnect-plugins', '/usr/share/locale', fallback=True)
        _ = t.ugettext
        self.setWindowTitle(_('Pause media players'))
        layout = self.contentLayout
        conditionGroupBox = QtGui.QGroupBox(_('Condition'))
        layout.addWidget(conditionGroupBox)
        conditionLayout = QtGui.QVBoxLayout()
        conditionGroupBox.setLayout(conditionLayout)
        self.conditionGroup = QtGui.QButtonGroup()
        conditionRingRadio = QtGui.QRadioButton(_('Pause as soon as phone rings'))
        self.conditionGroup.addButton(conditionRingRadio, 0)
        conditionTalkRadio = QtGui.QRadioButton(_('Pause only while talking'))
        self.conditionGroup.addButton(conditionTalkRadio, 1)
        conditionLayout.addWidget(conditionRingRadio)
        conditionLayout.addWidget(conditionTalkRadio)
        self.conditionGroup.button(self.settings.value('conditionTalking', self.defaults['conditionTalking']).toBool()).setChecked(True)

        actionsGroupBox = QtGui.QGroupBox(_('Actions'))
        layout.addWidget(actionsGroupBox)
        actionsLayout = QtGui.QVBoxLayout()
        actionsGroupBox.setLayout(actionsLayout)
        self.actionPauseChk = QtGui.QCheckBox(_('Pause media players'))
        actionsLayout.addWidget(self.actionPauseChk)
        self.actionPauseChk.setChecked(self.settings.value('actionPause', self.defaults['actionPause']).toBool())
        self.actionMuteChk = QtGui.QCheckBox(_('Mute system sound'))
        actionsLayout.addWidget(self.actionMuteChk)
        self.actionMuteChk.setChecked(self.settings.value('actionMute', self.defaults['actionMute']).toBool())
        self.restoreBtn.clicked.connect(lambda:
            (self.conditionGroup.button(int(self.defaults['conditionTalking'])).setChecked(True), 
            self.actionPauseChk.setChecked(True if self.defaults['actionPause'] else False), 
            self.actionMuteChk.setChecked(True if self.defaults['actionMute'] else False), 
            ))

    def apply(self):
        self.settings.setValue('conditionTalking', bool(self.conditionGroup.checkedId()))
        self.settings.setValue('actionPause', self.actionPauseChk.isChecked())
        self.settings.setValue('actionMute', self.actionMuteChk.isChecked())
        self.settings.sync()
        self.accept()


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
    def __init__(self, editable=True, *args, **kwargs):
        QtGui.QStyledItemDelegate.__init__(self, *args, **kwargs)
        self.editable = editable
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

    def editorEvent(self, event, model, option, index):
        if not self.editable:
            return False
        if index.flags() & QtCore.Qt.ItemIsEnabled:
            if event.type() == QtCore.QEvent.MouseButtonPress and event.button() == QtCore.Qt.LeftButton:
                state = index.data(QtCore.Qt.CheckStateRole).toBool()
                model.itemFromIndex(index).setData(not state, QtCore.Qt.CheckStateRole)
                if self.parent():
                    selection = self.parent().selectionModel()
                    selection.setCurrentIndex(index, selection.NoUpdate)
            if event.type() == QtCore.QEvent.KeyPress and event.key() in (QtCore.Qt.Key_Space, QtCore.Qt.Key_Enter):
                state = index.data(QtCore.Qt.CheckStateRole)
                model.itemFromIndex(index).setData(not state, QtCore.Qt.CheckStateRole)
        return True


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
        self.xpos = pos
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
        dateLines = []
        while nextSecs <= lastSecs:
            dateLines.append(self.addLine(nextSecs, 0, nextSecs, 100, self.dateLinePen))
            dateText = self.addText(nextDate.toString('dd/MM/yy'))
            dateText.setX(nextSecs)
            dateText.setFlag(dateText.ItemIgnoresTransformations, True)
            nextSecs += 86400
            nextDate = nextDate.addDays(1)
#        print self.views()
        firstLinePos = int(round(dateLines[0].boundingRect().x() / 1000.))
        firstDateString = firstDate.toString('dd/MM/yy')
        if QtGui.QFontMetrics(self.font()).width(firstDateString) < firstLinePos:
            firstDateText = self.addText(firstDateString)
            firstDateText.setFlag(firstDateText.ItemIgnoresTransformations, True)

    def itemActivated(self, id):
        old = self.activeItem
        if old is not None:
            old.pen = QtCore.Qt.NoPen
            old.update()
        self.activeItem = self.items[id]
        self.activeItem.pen = QtCore.Qt.blue
        self.update()


class HistoryDialog(QtGui.QDialog):
    def __init__(self, main):
        QtGui.QDialog.__init__(self)
        loadUi('history.ui', self)
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
        self.statusView.resizeEvent = self.statusViewResizeEvent
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

    def statusViewResizeEvent(self, event):
        origin = self.statusView.mapToScene(self.statusView.viewport().pos())
        self.statusView.fitInView(origin.x(), 0, event.size().width() * 1000, self.statusScene.sceneRect().height(), QtCore.Qt.IgnoreAspectRatio)

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
        self.statusView.ensureVisible(self.statusScene.activeItem)

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


class PluginsDialog(QtGui.QDialog):
    pluginDialogs = {
        'kdeconnect_pausemusic': PluginPauseMusic, 
        'kdeconnect_share': PluginShare, 
        'kdeconnect_runcommand': PluginRunCommands, 
#        'kdeconnect_sendnotifications': PluginSendNotifications, 
        }
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

        self.pluginsTable = QtGui.QTableWidget(len(propsIface.Get('org.kde.kdeconnect.device', 'supportedPlugins')), 3)
        layout.addWidget(self.pluginsTable)
#        self.pluginsModel = QtGui.QStandardItemModel()
#        self.pluginsTable.setModel(self.pluginsModel)
#        self.pluginsTable.setItemDelegateForColumn(1, CheckBoxDelegate())
        self.pluginsTable.setSelectionMode(self.pluginsTable.NoSelection)
        self.pluginsTable.setEditTriggers(self.pluginsTable.NoEditTriggers)
        self.pluginsTable.setVerticalScrollMode(self.pluginsTable.ScrollPerPixel)
        self.pluginsTable.horizontalHeader().setVisible(False)
        self.pluginsTable.verticalHeader().setVisible(False)
        availablePlugins = self.devIface.loadedPlugins()
        for row, plugin in enumerate(sorted(propsIface.Get('org.kde.kdeconnect.device', 'supportedPlugins'))):
            plugin = unicode(plugin)
            pluginName, pluginRequired, pluginEditable, pluginEnabled = KdeConnectPlugins[plugin]
            pluginItem = QtGui.QTableWidgetItem(pluginName)
            pluginItem.setData(PluginRole, plugin)
            pluginItem.setData(QtCore.Qt.ToolTipRole, KdeConnectPluginsDescriptions[plugin])
            self.pluginsTable.setItem(row, 1, pluginItem)

            editableItem = QtGui.QPushButton()
            editableItem.setIcon(QtGui.QIcon.fromTheme('preferences-other'))
            if pluginEditable:
                self.pluginsTable.setCellWidget(row, 2, editableItem)
                editableItem.clicked.connect(lambda state, plugin=plugin: self.showPluginDialog(plugin))

            selectableItem = QtGui.QTableWidgetItem()
            selectableItem.setFlags(selectableItem.flags() | QtCore.Qt.ItemIsUserCheckable)
            self.pluginsTable.setItem(row, 0, selectableItem)

            if plugin in availablePlugins:
                selectableItem.setCheckState(2)
                editableItem.setEnabled(True if pluginEnabled else False)
            else:
                selectableItem.setCheckState(0)
                editableItem.setEnabled(False)
            if pluginRequired:
                pluginItem.setFlags(pluginItem.flags() ^ QtCore.Qt.ItemIsEnabled)
                selectableItem.setFlags(selectableItem.flags() ^ QtCore.Qt.ItemIsEnabled)
        self.pluginsTable.resizeColumnsToContents()
        self.pluginsTable.resizeRowsToContents()
        self.pluginsTable.horizontalHeader().setResizeMode(0, QtGui.QHeaderView.Fixed)
        self.pluginsTable.horizontalHeader().setResizeMode(1, QtGui.QHeaderView.Stretch)
        self.pluginsTable.horizontalHeader().setResizeMode(2, QtGui.QHeaderView.Fixed)
        self.buttonBox = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok|QtGui.QDialogButtonBox.Cancel)
        self.okBtn = self.buttonBox.button(self.buttonBox.Ok)
        self.okBtn.setEnabled(False)
        self.pluginsTable.cellChanged.connect(self.dataChanged)
#        self.pluginsModel.dataChanged.connect(lambda *args: self.buttonBox.button(self.buttonBox.Ok).setEnabled(True))
        self.okBtn.clicked.connect(self.setPlugins)
        self.buttonBox.button(self.buttonBox.Cancel).clicked.connect(self.reject)
        layout.addWidget(self.buttonBox)

    def dataChanged(self, row, column):
        self.okBtn.setEnabled(True)
        selectableItem = self.pluginsTable.item(row, 0)
        plugin = self.pluginsTable.item(row, 1).data(PluginRole).toPyObject()
        enabled = selectableItem.data(QtCore.Qt.CheckStateRole).toBool()
        editableItem = self.pluginsTable.cellWidget(row, 2)
        pluginData = KdeConnectPlugins[unicode(plugin)]
        if editableItem and enabled and pluginData.editable and pluginData.enabled:
            editableItem.setEnabled(True)
        elif editableItem:
            editableItem.setEnabled(False)

    def showPluginDialog(self, plugin):
        config = QtCore.QFileInfo(self.devIface.pluginsConfigFile()).absolutePath() + '/{}/config'.format(plugin)
        res = self.pluginDialogs[plugin](self, config).exec_()
        if res:
            self.devIface.reloadPlugins()
            self.okBtn.setEnabled(True)

    def setPlugins(self):
        self.settings.beginGroup('plugins')
        for row in xrange(self.pluginsTable.rowCount()):
            selectableItem = self.pluginsTable.item(row, 0)
            if not selectableItem.flags() & QtCore.Qt.ItemIsEnabled:
                continue
            pluginItem = self.pluginsTable.item(row, 1)
            pluginNameFull = '{}Enabled'.format(pluginItem.data(PluginRole).toString())
            pluginState = selectableItem.data(QtCore.Qt.CheckStateRole).toBool()
            if pluginState != self.settings.value(pluginNameFull).toBool():
#                print pluginItem.text(), pluginItem.data(PluginRole).toString(), pluginState, self.settings.value(pluginNameFull).toBool()
                self.settings.setValue(pluginNameFull, pluginState)
        self.settings.endGroup()
        self.settings.sync()
        self.devIface.reloadPlugins()
        self.accept()


class TableIconDelegate(QtGui.QStyledItemDelegate):
    noIcon = QtGui.QIcon()
    def paint(self, painter, style, index):
        option = QtGui.QStyleOptionViewItemV4()
        option.__init__(style)
        self.initStyleOption(option, index)
        option.icon = self.noIcon
        QtGui.QApplication.style().drawControl(QtGui.QStyle.CE_ItemViewItem, option, painter)
        icon = index.data(QtCore.Qt.DecorationRole).toPyObject()
        if not icon:
            return
        pixmap = icon.pixmap(option.rect.size())
        p = QtCore.QPoint((option.rect.width() - pixmap.width()) / 2, (option.rect.height() - pixmap.height()) / 2)
        painter.drawPixmap(option.rect.topLeft() + p, pixmap)


class SettingsDialog(QtGui.QDialog):
    keepNotificationsChanged = QtCore.pyqtSignal(int, int)
    keepStatusChanged = QtCore.pyqtSignal(int, int)
    changedSignals = (
        'keepNotifications', 
        'keepStatus', 
        )

    def __init__(self, main):
        QtGui.QDialog.__init__(self)
        loadUi('settings.ui', self)
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

        self.tableIconDelegate = TableIconDelegate()
        self.appTable.setItemDelegateForColumn(1, self.tableIconDelegate)
        self.checkBoxDelegate = CheckBoxDelegate()
        self.appTable.setItemDelegateForColumn(2, self.checkBoxDelegate)
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
        self.tabWidget.setCurrentIndex(0)
        self.main.historyDialog.hide()
        self.readSettings()
        self.buttonBox.button(self.buttonBox.Apply).setEnabled(False)
        self.appModel.clear()
        self.appModel.setHorizontalHeaderLabels(['App name', 'Icon', 'Ignore'])
        ignored = self.settings.value('ignoredApps', []).toPyObject()
        try:
            ignored.split(',')
        except:
            pass
        self.settings.beginGroup('customIcons')
        self.appList = set()
        for app in sorted(self.settings.childKeys()):
            app = unicode(app)
            self.appList.add(app)
            appItem = QtGui.QStandardItem(app)
            customValue = unicode(self.settings.value(app).toString())
            if customValue and customValue != 'false':
                if customValue in self.main.defaultIcons:
                    icon = self.main.defaultIcons[customValue]
                else:
                    icon = QtGui.QIcon('{}/{}.png'.format(self.main.iconsPath, app))
                iconItem = QtGui.QStandardItem()
                iconItem.setData(icon, QtCore.Qt.DecorationRole)
                iconItem.setData(QtGui.QBrush(QtCore.Qt.lightGray), QtCore.Qt.BackgroundRole)
                iconItem.setData(app, IconNameRole)
#                iconItem.setData(iconName, QtCore.Qt.ToolTipRole)
            ignoredItem = QtGui.QStandardItem()
            ignoredItem.setData(2 if app in ignored else 2, QtCore.Qt.CheckStateRole)
            self.appModel.appendRow([appItem, iconItem, ignoredItem])
        defaults = {}
        unknown = {}
        for n in self.main.notificationsHistory:
            if n.app in self.appList:
                continue
            self.appList.add(n.app)
            appItem = QtGui.QStandardItem(n.app)
            iconItem = QtGui.QStandardItem()
            ignoredItem = QtGui.QStandardItem()
            ignoredItem.setData(2 if n.app in ignored else 0, QtCore.Qt.CheckStateRole)
            if n.app in self.main.defaultIcons:
                iconName = '{}.png'.format(n.app)
                iconItem.setData(self.main.defaultIcons[n.app], QtCore.Qt.DecorationRole)
                iconItem.setData(QtGui.QBrush(QtCore.Qt.lightGray), QtCore.Qt.BackgroundRole)
                iconItem.setData(QtCore.Qt.AlignCenter, QtCore.Qt.TextAlignmentRole)
                iconItem.setData(iconName, IconNameRole)
                iconItem.setData(iconName, QtCore.Qt.ToolTipRole)
                appItem.setData(QtGui.QBrush(QtCore.Qt.darkGray), QtCore.Qt.ForegroundRole)
                defaults[appItem] = [iconItem, ignoredItem]
            else:
                appItem.setData(QtGui.QBrush(QtCore.Qt.lightGray), QtCore.Qt.ForegroundRole)
                unknown[appItem] = [iconItem, ignoredItem]
#            self.appModel.appendRow([appItem, iconItem])
        for app in sorted(defaults):
            self.appModel.appendRow([app] + defaults[app])
        for app in sorted(unknown):
            self.appModel.appendRow([app] + unknown[app])
        self.settings.endGroup()
        self.appTable.resizeColumnToContents(1)
        self.appTable.resizeColumnToContents(2)
        self.appTable.horizontalHeader().setResizeMode(0, QtGui.QHeaderView.Stretch)
        self.appTable.horizontalHeader().setResizeMode(1, QtGui.QHeaderView.Fixed)
        self.appTable.horizontalHeader().setResizeMode(2, QtGui.QHeaderView.Fixed)
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
        ignored = []
        for row in xrange(self.appModel.rowCount()):
            app = self.appModel.item(row, SettingsAppTableApp).text()
            iconItem = self.appModel.item(row, SettingsAppTableIcon)
            ignoredItem = self.appModel.item(row, SettingsAppTableIgnore)
            if ignoredItem.data(QtCore.Qt.CheckStateRole).toBool():
                ignored.append(unicode(app))
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
                    if not QtCore.QFile.copy('{iconsPath}/{iconName}'.format(iconsPath=iconsPath, iconName=iconName), dest.fileName()):
                        print 'error saving {} to {}'.format(app, iconName)
                        return
                    self.settings.setValue(app, 'true')
#                    pm = QtGui.QPixmap(iconName).scaled(QtCore.QSize(12, 12), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
#                self.settings.setValue(app, iconItem.data(IconNameRole))
        self.settings.endGroup()
        if ignored:
            self.settings.setValue('ignoredApps', ','.join(ignored))
        else:
            self.settings.remove('ignoredApps')
        self.settings.sync()
        self.buttonBox.button(self.buttonBox.Apply).setEnabled(False)

    def readSettings(self):
        for w in self.widgetSignals:
                w.blockSignals(True)
        for item, data in settingsWidgets.items():
            if data.type == GROUP:
                radioBtn = getattr(self, '{}Group'.format(item)).button(int(self.settings.value(item, data.default).toPyObject()))
                #the slot is delayed (0: as soon as main loop is available) to ensure that signals are actually sent
                QtCore.QTimer.singleShot(0, lambda radioBtn=radioBtn: radioBtn.setChecked(True))
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
        self.okBtn = self.buttonBox.button(self.buttonBox.Ok)
        self.okBtn.setEnabled(False)
        self.okBtn.clicked.connect(self.accept)
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
        self.deviceTable.setItemDelegateForColumn(2, CheckBoxDelegate(False))
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
                    self.okBtn.setEnabled(True)
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
                self.okBtn.setEnabled(paired)
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
                self.okBtn.setEnabled(True)
            else:
                devItem.setEnabled(state)
                nameItem.setEnabled(state)
                pairedItem.setEnabled(state)
                self.pairBtn.setEnabled(True if state else False)
                self.okBtn.setEnabled(False)

    def checkPairing(self, index):
        if not index.isValid():
            self.pairBtn.setEnabled(False)
            return
        if not self.deviceModel.itemFromIndex(index).isEnabled():
            self.pairBtn.setEnabled(False)
            self.okBtn.setEnabled(False)
            return
        paired = index.sibling(index.row(), 2).data(QtCore.Qt.CheckStateRole).toBool()
        if paired:
            self.pairBtn.setEnabled(False)
            self.okBtn.setEnabled(True)
        else:
            self.pairBtn.setEnabled(True)
            self.okBtn.setEnabled(False)


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
        layout.addWidget(self.buttonBox)
        self.buttonBox.button(self.buttonBox.Cancel).clicked.connect(self.reject)

        self.restoreBtn = QtGui.QPushButton('Restore')
        self.restoreBtn.setIcon(QtGui.QIcon.fromTheme('edit-undo'))
        self.restoreBtn.clicked.connect(self.restorePlugins)
        self.buttonBox.addButton(self.restoreBtn, self.buttonBox.AcceptRole)

        self.reloadBtn = QtGui.QPushButton('Refresh list')
        self.reloadBtn.setIcon(QtGui.QIcon.fromTheme('view-refresh'))
        self.reloadBtn.clicked.connect(lambda: self.updatePlugins(None))
        self.buttonBox.addButton(self.reloadBtn, self.buttonBox.ActionRole)

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

    def updatePlugins(self, state=None):
        self.phone = self.main.phone
        if state is None:
            state = self.phone.hasMissingRequiredPlugins()
        if not self.phone.reachable or not state:
            self.hide()
            return
        _start = self.pluginsModel.index(0, 0)
#        missingPlugins = KdeConnectRequiredPlugins & set(map(unicode, self.phone.devIface.loadedPlugins())) ^ KdeConnectRequiredPlugins
        missingPlugins = [plugin for plugin in KdeConnectRequiredPlugins if not self.phone.hasPlugin(plugin)]
        if not missingPlugins:
            self.hide()
            return
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

