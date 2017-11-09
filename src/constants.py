#!/usr/bin/env python2.7
# *-* coding: utf-8 *-*

import os
import __main__
import re
from collections import namedtuple
from PyQt4 import QtCore

MAJ_VERSION = 0
MIN_VERSION = 9
REV_VERSION = 0
VERSION = '{}.{}.{}'.format(MAJ_VERSION, MIN_VERSION, REV_VERSION)

HIGH, LOW = 0, 1
UNREACHABLE, REACHABLE = 0, 1
_iconOn = 'file://' + os.path.join(os.path.dirname(__main__.__file__), 'icons', 'kdeconnect-tray-on.svg')
_iconOff = 'file://' + os.path.join(os.path.dirname(__main__.__file__), 'icons', 'kdeconnect-tray-off.svg')
stateIcons = _iconOff, _iconOn

urlRegex = re.compile(r'\s((?:http(?:s)?:\/\/|ftp:\/\/)?[\d\w\@]+\.(?:[\w]{2,5})(?:(?:[\/]*(?![\,\.\:\;]\s)[\S])*)*)+')

NotificationData = namedtuple('NotificationData', 'time app ticker id')
PluginsData = namedtuple('PluginsData', 'text required editable enabled')
PluginsData.__new__.__defaults__ = (False, False, True)
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
    'kdeconnect_pausemusic': PluginsData('Pause media on phone call', editable=True), 
    'kdeconnect_findmyphone': PluginsData('Find my phone'), 
    'kdeconnect_share': PluginsData('Share files, links and text', editable=True), 
    'kdeconnect_mpriscontrol': PluginsData('Media player control'), 
    'kdeconnect_ping': PluginsData('Ping the device'), 
    'kdeconnect_telephony': PluginsData('Phone call and messages'), 
    'kdeconnect_notifications': PluginsData('Notifications', True), 
    'kdeconnect_mousepad': PluginsData('Trackpad-like and keyboard control'), 
    'kdeconnect_sftp': PluginsData('File system browse'), 
    'kdeconnect_clipboard': PluginsData('Share clipboard content'), 
    'kdeconnect_sendnotifications': PluginsData('Show desktop notifications on the device', editable=True, enabled=False), 
    'kdeconnect_screensaver_inhibit': PluginsData('Disable screensaver'), 
    'kdeconnect_runcommand': PluginsData('Run commands', editable=True), 
    'kdeconnect_battery': PluginsData('Battery status', True), 
    }

KdeConnectRequiredPlugins = set(p for p, d in KdeConnectPlugins.items() if d.required)

KdeConnectPluginsDescriptions = {
    'kdeconnect_pausemusic': 'Pause media player whenever a phone call starts', 
    'kdeconnect_findmyphone': 'Make the device "ring", in case you lost it and cannot find it (not required, but suggested)', 
    'kdeconnect_share': 'Share files, links and text with the device', 
    'kdeconnect_mpriscontrol': 'Control the media player', 
    'kdeconnect_ping': '"Ping" the device, useful to check if it is actually connected and paired', 
    'kdeconnect_telephony': 'Receive notifications on phone calls and SMS messages', 
    'kdeconnect_notifications': 'Synchronize device notifications with this computer (required)', 
    'kdeconnect_mousepad': 'Control mouse and keyboard input from the remote device', 
    'kdeconnect_sftp': 'Browse the device file system', 
    'kdeconnect_clipboard': 'Share clipboard content between this computer and the device', 
    'kdeconnect_sendnotifications': 'Show desktop notifications on the device (requires SystemSettings configuration)', 
    'kdeconnect_screensaver_inhibit': 'Disable screensaver when device is reachable', 
    'kdeconnect_runcommand': 'Run local commands on this computer from the device', 
    'kdeconnect_battery': 'Synchronize the device battery status (required)', 
    }

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
