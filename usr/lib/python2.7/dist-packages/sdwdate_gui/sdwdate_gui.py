#! /usr/bin/env python

import sys
from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import QFileSystemWatcher as watcher
from PyQt4.QtCore import QThread
import subprocess
from subprocess import check_output, call
import pickle
import os
import signal
import time
import re


class RightClickMenu(QtGui.QMenu):

    def __init__(self, parent=None):
        QtGui.QMenu.__init__(self, "File", parent)

        icon = QtGui.QIcon('/usr/share/icons/sdwdate-gui/text-x-script.png')
        action = QtGui.QAction(icon, "Open sdwdate's log", self)
        action.triggered.connect(show_log)
        self.addAction(action)

        self.addSeparator()

        icon = QtGui.QIcon('/usr/share/icons/sdwdate-gui/system-reboot.png')
        text = 'Restart sdwdate - Gradually adjust the time'
        action = QtGui.QAction(icon, text, self)
        action.triggered.connect(restart_sdwdate)
        self.addAction(action)

        icon = QtGui.QIcon('/usr/share/icons/sdwdate-gui/system-reboot.png')
        text = 'Restart sdwdate - Instantly adjust the time.'
        action = QtGui.QAction(icon, text, self)
        action.triggered.connect(restart_fresh)
        self.addAction(action)

        icon = QtGui.QIcon('/usr/share/icons/sdwdate-gui/system-shutdown.png')
        action = QtGui.QAction(icon, "Stop sdwdate", self)
        action.triggered.connect(stop_sdwdate)
        self.addAction(action)

        icon = QtGui.QIcon('/usr/share/icons/sdwdate-gui/application-exit.png')
        action = QtGui.QAction(icon, "&Exit", self)
        action.triggered.connect(QtGui.qApp.quit)
        self.addAction(action)


class Update(QtCore.QObject):
    update_tip = QtCore.pyqtSignal()


class SdwdateTrayIcon(QtGui.QSystemTrayIcon):

    def __init__(self, parent=None):
        QtGui.QSystemTrayIcon.__init__(self, parent)

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
            self.watcher = watcher([self.status_path])
            self.watcher.fileChanged.connect(self.status_changed)
        else:
            self.setIcon(QtGui.QIcon('/usr/share/icons/oxygen/16x16/status/dialog-error.png'))
            error_msg = '''<b>sdwdate is not running</b><br>
                           Try to restart it: Right click -> Restart sdwdate<br>
                           If the icon stays red, please report this bug.'''
            self.message = error_msg
            self.setToolTip(error_msg)
            self.watcher_2 = watcher([self.path])
            self.watcher_2.directoryChanged.connect(self.watch_folder)

    def run_popup(self):
        run_popup = ('%s "%s" %s %s &'
                % (self.popup_path, self.message, self.pos_x, self.pos_y))
        call(run_popup, shell=True)

    def show_message(self, caller):
        ## Store own positon for message gui.
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
            QtGui.QToolTip.showText(QtGui.QCursor.pos(),
                                   '%s\n%s' %(self.title, self.stripped_message))
        ## Do not show message on loading.
        if self.clicked_once:
            ## Update message only if already shown.
            if self.is_popup_running():
                self.show_message('update')

    def status_changed(self):
        ## Prevent race condition.
        ## Likely due to the issue below.
        time.sleep(0.01)

        with open(self.status_path, 'rb') as f:
            status = pickle.load(f)

        self.setIcon(QtGui.QIcon(status['icon']))
        self.message = status['message']
        self.stripped_message = re.sub('<[^<]+?>', '', self.message)

        ## QFileSystemWatcher may emit the fileChanged signal twice
        ## or three times, randomly. Filter to allow enough time
        ## between kill and restart popup in show_message(), and
        ## prevent os.kill to raise an error and leave a gui open.
        if self.message != self.previous_message:
            self.setToolTip('%s\n%s' %(self.title, self.stripped_message))
            self.update.update_tip.emit()
        self.previous_message = self.message

    def watch_folder(self):
        self.watcher = watcher([self.status_path])
        self.watcher.fileChanged.connect(self.status_changed)


def show_log():
    show_konsole = ('konsole --hold --hide-menubar --hide-tabbar ' +
           '-e "tail -f -n 100 /var/log/sdwdate.log"')
    call(show_konsole, shell=True)

def restart_sdwdate():
    call('sudo service sdwdate restart', shell=True)

def restart_fresh():
    if os.path.exists('/var/run/sdwdate/success'):
        call('sudo rm /var/run/sdwdate/success', shell=True)
    call('sudo service sdwdate restart', shell=True)

def stop_sdwdate():
    call('sudo service sdwdate stop', shell=True)

def main():
    app = QtGui.QApplication([])
    sdwdate_tray = SdwdateTrayIcon()
    sdwdate_tray.show()
    app.exec_()

if __name__ == "__main__":
    main()
