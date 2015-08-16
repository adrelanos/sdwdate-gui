#! /usr/bin/env python

from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import QFileSystemWatcher as watcher
import subprocess
from subprocess import check_output, call
import pickle
import os
import time


class RightClickMenu(QtGui.QMenu):

    def __init__(self, parent=None):
        QtGui.QMenu.__init__(self, "File", parent)

        #icon = QtGui.QIcon.fromTheme('dialog-information')
        #action = QtGui.QAction(icon, "View status", self)
        ##action.triggered.connect(restart_sdwdate)
        #self.addAction(action)

        icon = QtGui.QIcon.fromTheme('text-x-script')
        action = QtGui.QAction(icon, "Open sdwdate's log", self)
        #action.triggered.connect(restart_sdwdate)
        self.addAction(action)

        self.addSeparator()

        icon = QtGui.QIcon.fromTheme('system-reboot')
        text = 'Restart sdwdate - Gradually adjust the time'
        action = QtGui.QAction(icon, text, self)
        action.triggered.connect(restart_sdwdate)
        self.addAction(action)

        icon = QtGui.QIcon.fromTheme('system-reboot')
        text = 'Restart sdwdate - Instantly adjust the time.'
        action = QtGui.QAction(icon, text, self)
        action.triggered.connect(restart_sdwdate)
        self.addAction(action)

        icon = QtGui.QIcon.fromTheme('system-shutdown')
        action = QtGui.QAction(icon, "Stop sdwdate", self)
        #action.triggered.connect(restart_sdwdate)
        self.addAction(action)

        icon = QtGui.QIcon.fromTheme("application-exit")
        action = QtGui.QAction(icon, "&Exit", self)
        action.triggered.connect(QtGui.qApp.quit)
        self.addAction(action)


class Update(QtCore.QObject):

    update_tip = QtCore.pyqtSignal()


class SdwdateTrayIcon(QtGui.QSystemTrayIcon):

    def __init__(self, parent=None):
        QtGui.QSystemTrayIcon.__init__(self, parent)

        self.setIcon(QtGui.QIcon('/home/user/IconApproved.png'))

        self.right_click_menu = RightClickMenu()
        self.setContextMenu(self.right_click_menu)

        self.path = '/var/run/sdwdate'
        self.status_path = '/var/run/sdwdate/status'
        self.message = ''

        self.update = Update(self)
        self.update.update_tip.connect(self.update_tooltip)

        if os.path.exists(self.status_path):
            ## Read status when GUI is loaded.
            self.status_changed()
            self.setToolTip(self.message)
            self.watcher = watcher([self.status_path])
            self.watcher.fileChanged.connect(self.status_changed)
        else:
            self.setIcon(QtGui.QIcon.fromTheme('dialog-error'))
            msg = ('Time Synchronisation Monitor\n' +
                   'sdwdate not running\n' +
                   'Try to restart it: Right click -> Restart sdwdate\n' +
                   'If the icon stays red, please report this bug.')
            self.message = msg
            self.setToolTip(msg)
            self.watcher_2 = watcher([self.path])
            self.watcher_2.directoryChanged.connect(self.watch_folder)

        self.activated.connect(self.show_status)

    def show_status(self, reason):
        if reason == self.Trigger: # left click
            self.showMessage('Time Synchronisation Monitor', self.message)

    def update_tooltip(self):
        if self.geometry().contains(QtGui.QCursor.pos()):
            QtGui.QToolTip.showText(QtGui.QCursor.pos(), self.message)

    def status_changed(self):
        ## Prevent race condition.
        time.sleep(0.01)
        with open(self.status_path, 'rb') as f:
            status = pickle.load(f)

        self.setIcon(QtGui.QIcon(status['icon']))
        self.message = 'Time Synchronisation Monitor\n' + status['message']
        self.setToolTip(self.message)
        self.update.update_tip.emit()

    def watch_folder(self):
        self.watcher = watcher([self.status_path])
        self.watcher.fileChanged.connect(self.status_changed)


def restart_sdwdate():
    call('sudo systemctl restart sdwdate', shell=True)

def restart_fresh():
    pass

def main():
    app = QtGui.QApplication([])
    sdwdate_tray = SdwdateTrayIcon()
    sdwdate_tray.show()
    app.exec_()

if __name__ == "__main__":
    main()
