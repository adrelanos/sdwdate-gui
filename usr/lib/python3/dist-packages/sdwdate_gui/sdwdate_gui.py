#!/usr/bin/python3 -u

import sys
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import QFileSystemWatcher as watcher
from PyQt5.QtCore import QThread
import subprocess
from subprocess import check_output, call, Popen
import pickle
import os
import signal
import time
import re

import signal
signal.signal(signal.SIGINT, signal.SIG_DFL)

class RightClickMenu(QtWidgets.QMenu):

    def __init__(self, parent=None):
        QtWidgets.QMenu.__init__(self, "File", parent)

        icon = QtGui.QIcon('/usr/share/icons/sdwdate-gui/text-x-script.png')
        action = QtWidgets.QAction(icon, "Open sdwdate's log", self)
        action.triggered.connect(show_log)
        self.addAction(action)

        self.addSeparator()

        icon = QtGui.QIcon('/usr/share/icons/sdwdate-gui/system-reboot.png')
        text = 'Restart sdwdate'
        action = QtWidgets.QAction(icon, text, self)
        action.triggered.connect(restart_sdwdate)
        self.addAction(action)

        icon = QtGui.QIcon('/usr/share/icons/sdwdate-gui/system-shutdown.png')
        action = QtWidgets.QAction(icon, "Stop sdwdate", self)
        action.triggered.connect(stop_sdwdate)
        self.addAction(action)

        icon = QtGui.QIcon('/usr/share/icons/sdwdate-gui/application-exit.png')
        action = QtWidgets.QAction(icon, "&Exit", self)
        action.triggered.connect(sys.exit)
        self.addAction(action)


class Update(QtCore.QObject):
    update_tip = QtCore.pyqtSignal()


class SdwdateTrayIcon(QtWidgets.QSystemTrayIcon):

    def __init__(self, parent=None):
        QtWidgets.QSystemTrayIcon.__init__(self, parent)

        self.title = 'Time Synchronisation Monitor'
        self.right_click_menu = RightClickMenu()
        self.setContextMenu(self.right_click_menu)

        self.path = '/var/run/sdwdate'
        self.status_path = '/var/run/sdwdate/status'
        self.popup_path = '/usr/lib/sdwdate-gui/show_message'
        self.popup_pid = 0

        self.update = Update(self)
        self.update.update_tip.connect(self.update_tip)

        self.activated.connect(self.mouse_event)

        self.message_showing = False
        self.clicked_once = False
        self.pos_x = 0
        self.pos_y = 0

        self.message = ''
        self.previous_message = ''
        self.stripped_message = ''

        if os.path.exists(self.status_path):
            ## Read status when GUI is loaded.
            self.status_changed()
            self.watch_file()
        else:
            self.setIcon(QtGui.QIcon('/usr/share/icons/sdwdate-gui/620px-Ambox_outdated.svg.png'))
            error_msg = 'sdwdate will probably start in a few moments.'
            self.message = error_msg
            self.setToolTip(error_msg)
            self.watcher_2 = watcher([self.path])
            self.watcher_2.directoryChanged.connect(self.watch_folder)

    def run_popup(self):
        run_popup = ('%s "%s" %s %s &'
                % (self.popup_path, self.message, self.pos_x, self.pos_y))
        call(run_popup, shell=True)

    def show_message(self, caller):
        ## Store own position for message gui.
        if not self.clicked_once:
            self.pos_x = QtGui.QCursor.pos().x() - 50
            self.pos_y = QtGui.QCursor.pos().y() - 50
            self.clicked_once = True

        if self.is_popup_running():
            ## Kill message gui
            os.kill(self.popup_pid, signal.SIGTERM)
            if caller == 'update':
                self.run_popup()
        else:
            self.run_popup()

    def mouse_event(self, reason):
        ## Left click.
        if reason == self.Trigger:
            self.show_message('user')

    def is_popup_running(self):
        try:
            ## command exit code != 0 if path does not exists.
            cmd = ['pgrep', '-f', self.popup_path]
            self.popup_pid = int(check_output(cmd))
            return True
        except subprocess.CalledProcessError:
            return False

    def update_tip(self):
        ## Update tooltip if mouse on icon.
        if self.geometry().contains(QtGui.QCursor.pos()):
            QtWidgets.QToolTip.showText(QtGui.QCursor.pos(),
                                   '%s\n%s' %(self.title, self.stripped_message))
        ## Do not show message on loading.
        if self.clicked_once:
            ## Update message only if already shown.
            if self.is_popup_running():
                self.show_message('update')

    def status_changed(self):
        ## When the file is quickly rewritten by another operation, reading
        ## would fail. TOCTOU
        try:
            with open(self.status_path, 'rb') as f:
                status = pickle.load(f)
        except:
            return

        self.setIcon(QtGui.QIcon(status['icon']))
        ## Remove double quotes from message as they would be interpreted as
        ## an argument separator in /usr/lib/sdwdate-gui/show_message (called
        ## by run_popup).
        self.message = status['message'].replace('\"', '')
        self.stripped_message = re.sub('<[^<]+?>', '', self.message)

        ## QFileSystemWatcher may emit the fileChanged signal twice
        ## or three times, randomly. Filter to allow enough time
        ## between kill and restart popup in show_message(), and
        ## prevent os.kill to raise an error and leave a gui open.
        if self.message != self.previous_message:
            self.setToolTip('%s\n%s' %(self.title, self.stripped_message))
            self.update.update_tip.emit()
        self.previous_message = self.message

    def watch_file(self):
        self.watcher = watcher([self.status_path])
        self.watcher.fileChanged.connect(self.status_changed)

    def watch_folder(self):
        if os.path.exists(self.status_path):
            self.watcher_2.removePath(self.path)
            self.status_changed()
            self.watch_file()


def show_log():
    show_konsole = ('konsole --hold ' +
           '-e "tail -f -n 100 /var/log/sdwdate.log"')
    Popen(show_konsole, shell=True)

def restart_sdwdate():
    if os.path.exists('/var/run/sdwdate/success'):
        Popen('sudo --non-interactive rm /var/run/sdwdate/success', shell=True)
    Popen('sudo --non-interactive systemctl --no-pager --no-block restart sdwdate', shell=True)

def stop_sdwdate():
    Popen('sudo --non-interactive systemctl --no-pager --no-block stop sdwdate', shell=True)

def main():
    app = QtWidgets.QApplication(["Sdwdate"])
    sdwdate_tray = SdwdateTrayIcon()
    sdwdate_tray.show()
    app.exec_()

if __name__ == "__main__":
    main()
