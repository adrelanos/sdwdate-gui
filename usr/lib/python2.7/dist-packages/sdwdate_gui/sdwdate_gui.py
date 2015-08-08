#! /usr/bin/env python

from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import QFileSystemWatcher as watcher
import subprocess
from subprocess import check_output, call
import pickle


class SdwdateTrayMenu(QtGui.QMenu):

    def __init__(self, parent=None):
        QtGui.QMenu.__init__(self, "File", parent)

        icon = QtGui.QIcon.fromTheme('system-reboot')
        action = QtGui.QAction(icon, "Restart sdwdate", self)
        action.triggered.connect(restart_sdwdate)
        self.addAction(action)

        #icon = QtGui.QIcon("/usr/share/icons/anon-icon-pack/timesync.ico")
        #action = QtGui.QAction(icon, "Restart fresh (set time from web date)", self)
        #action.triggered.connect(restart_fresh)
        #self.addAction(action)

        icon = QtGui.QIcon.fromTheme("application-exit")
        action = QtGui.QAction(icon, "&Exit", self)
        action.triggered.connect(QtGui.qApp.quit)
        self.addAction(action)


class SdwdateTrayIcon(QtGui.QSystemTrayIcon):

    def __init__(self, parent=None):
        QtGui.QSystemTrayIcon.__init__(self, parent)

        self.setIcon(QtGui.QIcon('/home/user/IconApproved.png'))

        self.right_click_menu = SdwdateTrayMenu()
        self.setContextMenu(self.right_click_menu)
        self.setToolTip('Secure Network Time Synchronisation')

        self.check_bootclockrandomization()

        if self.check_sdwdate():
            self.path = '/var/run/sdwdate/status'
            ## Read status when gui is loaded.
            self.status_changed()

            self.watcher = watcher([self.path])
            self.watcher.fileChanged.connect(self.status_changed)
        else:
            self.setIcon(QtGui.QIcon.fromTheme('dialog-error'))
            message = ('Time Synchronisation Monitor\n' +
                       'sdwdate is not running.\n' +
                       'Please check sdwdate status, then exit and\n' +
                       'restart Time Synchronization Monitor.')
            self.setToolTip(message)

    def check_bootclockrandomization(self):
        try:
            status = check_output(['systemctl', 'status', 'bootclockrandomization'])
        except subprocess.CalledProcessError:
            message = 'bootclockrandomization failed.'
            print message

    def check_sdwdate(self):
        try:
            status = check_output(['systemctl', 'status', 'sdwdate'])
            return True
        except subprocess.CalledProcessError:
            return False

    def status_changed(self):
        with open(self.path, 'rb') as f:
            status = pickle.load(f)

        self.setIcon(QtGui.QIcon(status['icon']))

        self.setToolTip('Secure Network Time Synchronisation\n' +
                        status['message'])


def restart_sdwdate():
    call('sudo systemctl restart sdwdate', shell=True)

def restart_fresh():
    pass

def main():
    app = QtGui.QApplication([])
    timesync_icon = SdwdateTrayIcon()
    timesync_icon.show()
    app.exec_()

if __name__ == "__main__":
    main()
