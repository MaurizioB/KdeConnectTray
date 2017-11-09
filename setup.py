#!/usr/bin/env python
# -*- coding: utf-8 -*-

from sys import exit
try:
    print 'Checking for PyQt4...'
    import PyQt4
except:
    print 'PL2Edit requires PyQt4 to work! :('
    print 'Since setuptools is not able to install PyQt4, you have to install it manually...\n'
    print 'Sorry for the inconvenience.'
    exit()

from os import path
from setuptools import setup, find_packages

_path = path.abspath(path.dirname(__file__))
with open(path.join(_path, 'README.rst')) as f:
    long_desc = f.read()

info = {}
with open(path.join(_path, 'src/info.py')) as f:
    exec(f.read(), info)


setup(
    name="KdeConnectTray",
    version=info['__version__'],
    description="KdeConnect System Tray tool for non-kde environments",
    long_description=long_desc, 
    author="Maurizio Berti",
    author_email="maurizio.berti@gmail.com",
    url=info["__codeurl__"],
    classifiers=[
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Development Status :: 4 - Beta",
        "Environment :: X11 Applications :: Qt",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Topic :: Utilities"
    ],
    packages=['src', 'dialogs', 'icons'],
    include_package_data=True, 
    scripts=[
        "KdeConnectTray", 
        "KdeConnectTray.py", 
    ],
)
