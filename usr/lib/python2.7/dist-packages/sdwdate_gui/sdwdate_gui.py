#! /usr/bin/env python
from PyQt4 import QtGui
from PyQt4.QtCore import QThread, pyqtSignal, QString
import os
import time
import subprocess
from subprocess import check_output, call


class TimesyncMenu(QtGui.QMenu):

    def __init__(self, parent=None):
        QtGui.QMenu.__init__(self, "File", parent)

        icon = QtGui.QIcon.fromTheme('system-reboot')
        action = QtGui.QAction(icon, "Restart sdwdate", self)
        action.triggered.connect(restart_sdwdate)
        self.addAction(action)

        icon = QtGui.QIcon("/usr/share/icons/anon-icon-pack/timesync.ico")
        action = QtGui.QAction(icon, "Restart fresh (set time from web date)", self)
        action.triggered.connect(restart_fresh)
        self.addAction(action)

        icon = QtGui.QIcon.fromTheme("application-exit")
        action = QtGui.QAction(icon, "&Exit", self)
        action.triggered.connect(QtGui.qApp.quit)
        self.addAction(action)


class TimesyncTrayIcon(QtGui.QSystemTrayIcon):

    def __init__(self, parent=None):
        QtGui.QSystemTrayIcon.__init__(self, parent)

        self.setIcon(QtGui.QIcon("/usr/share/icons/anon-icon-pack/timesync.ico"))

        self.right_click_menu = TimesyncMenu()
        self.setContextMenu(self.right_click_menu)
        self.setToolTip('Secure Network Time Synchronisation')

        self.read_status = self.ReadSdwdateOutput()
        self.read_status.newStatus.connect(self.status_received)
        self.read_status.start()

        self.check_bootclockrandomization()
        self.check_sdwdate()

    def check_bootclockrandomization(self):
        try:
            status = check_output(['systemctl', 'status', 'bootclockrandomization'])
        except subprocess.CalledProcessError:
            message = 'bootclockrandomization failed.'
            self.status_received(message)

    def check_sdwdate(self):
        try:
            status = check_output(['systemctl', 'status', 'sdwdate'])
        except subprocess.CalledProcessError:
            message = 'sdwdate is not running.'
            self.status_received(message)

    def status_received(self, arg):
        #print(arg)
        pass
        #self.setIcon(QtGui.QIcon.fromTheme("media-skip-backward"))


    class ReadSdwdateOutput(QThread):

        newStatus = pyqtSignal(QString)

        def run(self):
            while True:
                file_name = '/tmp/sdwdate/last_output'
                if os.path.exists(file_name):
                    f = open(file_name, 'r')
                    output = f.read()
                    f.close()
                    os.remove(file_name)
                    self.newStatus.emit(output)
                time.sleep(0.5)


def restart_sdwdate():
    call('sudo systemctl restart sdwdate', shell=True)

def restart_fresh():
    pass

def main():
    a = 0
    app = QtGui.QApplication([])
    timesync_icon = TimesyncTrayIcon()
    timesync_icon.show()
    app.exec_()

if __name__ == "__main__":
    main()
