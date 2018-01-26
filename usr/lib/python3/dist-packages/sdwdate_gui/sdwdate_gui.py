#!/usr/bin/python3 -u

## Copyright (C) 2015 - 2017 Patrick Schleizer <adrelanos@riseup.net>
## See the file COPYING for copying conditions.

import sys
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import QFileSystemWatcher
from PyQt5.QtCore import QThread
from PyQt5.QtCore import QProcess
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
        self.msg_path = '/var/run/sdwdate/msg'
        self.icon_path = '/var/run/sdwdate/status'
        self.show_message_path = '/usr/lib/sdwdate-gui/show_message'
        self.popup_process = None

        self.success_icon = '/usr/share/icons/sdwdate-gui/Ambox_currentevent.svg.png'
        self.busy_icon = '/usr/share/icons/sdwdate-gui/620px-Ambox_outdated.svg.png'
        self.error_icon = '/usr/share/icons/sdwdate-gui/212px-Timeblock.svg.png'

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

        self.setIcon(QtGui.QIcon('/usr/share/icons/sdwdate-gui/620px-Ambox_outdated.svg.png'))
        startup_msg = 'sdwdate will probably start in a few moments.'
        self.message = startup_msg
        self.setToolTip(startup_msg)

        self.status_changed()

        self.watcher_file = QFileSystemWatcher([self.msg_path])
        self.watcher_file.fileChanged.connect(self.status_changed)

    def run_popup(self):
        popup_process_cmd = ('%s "%s" %s %s'
                % (self.show_message_path, self.pos_x, self.pos_y, self.message))
        self.popup_process = QProcess()
        self.popup_process.start(popup_process_cmd)

    def show_message(self, caller):
        ## Store own position for message gui.
        if not self.clicked_once:
            self.pos_x = QtGui.QCursor.pos().x() - 50
            self.pos_y = QtGui.QCursor.pos().y() - 50
            self.clicked_once = True

        if self.popup_process == None:
            self.run_popup()
            return

        if self.popup_process.pid() > 0:
            try:
                  self.popup_process.kill()
            except:
                  pass
            self.popup_process = None
            if caller == 'update':
                self.run_popup()
        else:
            self.run_popup()

    def mouse_event(self, reason):
        ## Left click.
        if reason == self.Trigger:
            self.show_message('user')

    def update_tip(self):
        ## Update tooltip if mouse on icon.
        if self.geometry().contains(QtGui.QCursor.pos()):
            QtWidgets.QToolTip.showText(QtGui.QCursor.pos(),
                                   '%s\n%s' %(self.title, self.stripped_message))

        if self.popup_process == None:
            return

        ## Update message only if already shown.
        if self.popup_process.pid() > 0:
            self.show_message('update')

    def status_changed(self):
        ## could fail if self.msg_path,
        ## - is still empty (sdwdate has not been started yet)
        ## - contains invalid contents (if sdwdate got killed the moment it was
        ##   writing to that file.
        try:
            with open(self.msg_path, 'rb') as f:
                msg = f.read()
        except:
            error_msg = "Unexpected error msg_path read: " + str(sys.exc_info()[0])
            print(error_msg)
            return
        try:
            with open(self.icon_path, 'rb') as f:
                icon_type = f.read()
        except:
            error_msg = "Unexpected error icon_path read: " + str(sys.exc_info()[0])
            print(error_msg)
            return

        if icon_type == bytes("error", encoding = 'utf-8'):
            status = self.error_icon
        elif icon_type == bytes("busy", encoding = 'utf-8'):
            status = self.busy_icon
        elif icon_type == bytes("success", encoding = 'utf-8'):
            status = self.success_icon
        else:
            status = self.error_icon
            print("ERROR: unknown icon_type: ", icon_type)

        self.setIcon(QtGui.QIcon(status))
        self.message = msg

        self.setToolTip('%s\n%s' %(self.title, self.message))
        self.update.update_tip.emit()


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
