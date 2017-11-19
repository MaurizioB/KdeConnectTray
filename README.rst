KdeConnectTray
==============

This program allows you to use Kde's "KdeConnect" features on any environment 
that supports System Tray Icons.

While KdeConnectTray is able to configure KdeConnect by itself, some plugins 
will still need Kde's SystemSettings.

Features
--------

- Device pairing, without the need of Kde's SystemSettings (which is still
  required for *some* plugins custom configuration).
- Device notifications management.
- Energy monitoring (battery status and charge/discharge extimation)
- Usage and notification statistics

Requirements
------------
- Python 2.7
- python-dbus >= 1.2.0
- PyQt4 >= 4.11.1
- KdeConnect >= 1.0.3
- KdeConnect app installed on the device. You can find it on `Google Play`_ or
  on F-Droid_.

.. _Google Play: https://play.google.com/store/apps/details?id=org.kde.kdeconnect_tp
.. _F-Droid: https://f-droid.org/repository/browse/?fdid=org.kde.kdeconnect_tp

Installation
------------

Installation is optional (the script can be run from the main directory), but
raccomanded.

Standard system installation:

``sudo ./setup.py install``

Single user installation:

``./setup.py install --user``

If you want to keep track of installed files, append ``--record files.txt`` to 
the command line. If you want to delete it afterwards, just run:

``cat files.txt | xargs -d '\n' rm -rf``

Usage
-----

If you didn't follow the installation procedure, run ``./KdeConnectTray`` from
the main directory where you cloned the project.
Otherwise, just launch ``KdeConnectTray`` as any other installed program.

Once started it will try to find available devices in the current network with 
the KdeConnect app installed. Select the device and press "Ok". If the device has
not been paired ("associated") yet, press "Pair" and accept the request on the
device, then press Ok.
The device will be rembered, but you can change it in the settings dialog (right
click on the tray icon).
