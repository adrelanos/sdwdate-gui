#!/usr/bin/python3 -u

## Copyright (C) 2015 - 2023 ENCRYPTED SUPPORT LP <adrelanos@whonix.org>
## See the file COPYING for copying conditions.

import sys
import signal
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QMenu, QAction
from PyQt5.QtCore import *
import subprocess
import json
import os
import re
import glob

anon_connection_wizard_installed = os.path.exists('/usr/bin/anon-connection-wizard')
if anon_connection_wizard_installed:
    from anon_connection_wizard import tor_status


class SdwdateTrayIcon(QtWidgets.QSystemTrayIcon):
    def __init__(self, parent=None):
        QtWidgets.QSystemTrayIcon.__init__(self, parent)

        self.title = 'Time Synchronisation Monitor'

        self.status_path =          '/run/sdwdate/status'
        self.anon_status_path =     '/run/sdwdate-gui/anon-status'
        self.show_message_path =    '/usr/libexec/sdwdate-gui/show_message'
        self.tor_path =             '/run/tor'
        self.tor_running_path =     '/run/tor/tor.pid'
        self.torrc_path =           '/usr/local/etc/torrc.d/'

        self.popup_process = None

        self.clicked_once = False
        self.pos_x = 0
        self.pos_y = 0

        self.icon_path = '/usr/share/sdwdate-gui/icons/'

        self.tor_icon = [self.icon_path + 'tor-ok.png',
                         self.icon_path + 'tor-error.png',
                         self.icon_path + 'tor-error.png',
                         self.icon_path + 'tor-warning.png']

        self.tor_status_list = ['running',
                                'stopped',
                                'disabled',
                                'disabled-running']

        self.tor_status = 'stopped'
        self.tor_message =  ''
        self.is_tor_message = False

        self.icon = [self.icon_path + 'sdwdate-success.png',
                     self.icon_path + 'sdwdate-wait.png',
                     self.icon_path + 'sdwdate-stopped.png']

        self.sdwdate_status = 'busy'
        self.sdwdate_message = 'Waiting for first sdwdate status...'
        self.status_list = ['success', 'busy', 'error']

        self.setIcon(QtGui.QIcon(self.icon[self.status_list.index('busy')]))
        self.setToolTip('Time Synchronisation Monitor \n Click for menu.')

        if anon_connection_wizard_installed:
            self.tor_watcher = QFileSystemWatcher([self.tor_path, self.torrc_path])
            self.tor_watcher.directoryChanged.connect(self.tor_status_changed)
        else:
            self.tor_status = 'running'

        self.sdwdate_watcher = QFileSystemWatcher([self.status_path])
        self.sdwdate_watcher.fileChanged.connect(self.status_changed)

        self.menu = QMenu()
        self.create_menu()
        self.setContextMenu(self.menu)
        self.activated.connect(self.show_menu)

        self.tor_status_changed()
        self.status_changed()

    def show_menu(self, event):
        if event == self.Trigger:
            self.menu.exec_(QtGui.QCursor.pos())

    def create_menu(self):
        advanced_icon = QtGui.QIcon(self.icon_path + 'advancedsettings.ico')

        if anon_connection_wizard_installed:
            icon = QtGui.QIcon(self.tor_icon[self.tor_status_list.index(self.tor_status)])
            action = QtWidgets.QAction(icon, 'Show Tor status', self)
            action.triggered.connect(lambda: self.show_message('tor'))
            self.menu.addAction(action)
            action = QtWidgets.QAction(advanced_icon, 'Tor control panel', self)
            action.triggered.connect(self.show_tor_status)
            self.menu.addAction(action)
            self.menu.addSeparator()

        icon = QtGui.QIcon(self.icon[self.status_list.index('busy')])
        action = QtWidgets.QAction(icon, 'Show sdwdate status', self)
        action.triggered.connect(lambda: self.show_message('sdwdate'))
        self.menu.addAction(action)

        self.menu.addSeparator()

        icon = QtGui.QIcon(self.icon_path + 'sdwdate-log.png')
        action = QtWidgets.QAction(icon, "Open sdwdate's log", self)
        action.triggered.connect(self.show_sdwdate_log)
        self.menu.addAction(action)

        icon = QtGui.QIcon(self.icon_path + 'restart-sdwdate.png')
        text = 'Restart sdwdate'
        action = QtWidgets.QAction(icon, text, self)
        action.triggered.connect(self.restart_sdwdate)
        self.menu.addAction(action)

        ## TODO: wait until file self.status_path is created

        self.watcher_file = QFileSystemWatcher([self.status_path])
        self.watcher_file.fileChanged.connect(self.status_changed)

        icon = QtGui.QIcon(self.icon_path + 'stop-sdwdate.png')
        action = QtWidgets.QAction(icon, "Stop sdwdate", self)
        action.triggered.connect(self.stop_sdwdate)
        self.menu.addAction(action)

        self.menu.addSeparator()
        icon = QtGui.QIcon('/usr/share/icons/sdwdate-gui/application-exit.png')
        action = QAction(icon, "&Exit", self)
        action.triggered.connect(sys.exit)
        self.menu.addAction(action)

    def update_menu(self):
        sdwdate_icon = QtGui.QIcon(self.icon[self.status_list.index(self.sdwdate_status)])
        tor_icon = QtGui.QIcon(self.tor_icon[self.tor_status_list.index(self.tor_status)])

        if anon_connection_wizard_installed:
            self.menu.actions()[0].setIcon(tor_icon)
            self.menu.actions()[3].setIcon(sdwdate_icon)
        else:
            self.menu.actions()[0].setIcon(sdwdate_icon)

    def run_popup(self, caller):
        if caller == 'tor':
            popup_process_cmd = ('%s %s %s %s' % (self.show_message_path, self.pos_x, self.pos_y,
                    '"%s" "%s"' % (self.tor_message, self.tor_icon[self.tor_status_list.index(self.tor_status)])))
        elif caller == 'sdwdate':
            popup_process_cmd = ('%s %s %s %s' % (self.show_message_path, self.pos_x, self.pos_y,
                    '"Last message from sdwdate:<br><br>%s" "%s"' % (self.sdwdate_message,
                    self.icon[self.status_list.index(self.sdwdate_status)])))

        self.popup_process = QProcess()
        self.popup_process.start(popup_process_cmd)

    def show_message(self, caller):
        ## Store own position for message gui.
        if not self.clicked_once:
            self.pos_x = QtGui.QCursor.pos().x() - 50
            self.pos_y = QtGui.QCursor.pos().y() - 50
            self.clicked_once = True

        if self.popup_process == None:
            self.run_popup(caller)
            return

        if self.popup_process.pid() > 0:
            self.popup_process.kill()
            self.popup_process = None
            self.run_popup(caller)
        else:
            self.run_popup(caller)

    def update_tip(self, caller):
        if self.popup_process == None:
            return

        ## Update message only if already shown.
        if self.popup_process.pid() > 0:
            self.show_message(caller)

    def set_tray_icon(self):
        if self.tor_status == 'running':
            self.setIcon(QtGui.QIcon(self.icon[self.status_list.index(self.sdwdate_status)]))
        else:
            self.setIcon(QtGui.QIcon(self.tor_icon[self.tor_status_list.index(self.tor_status)]))

    def parse_sdwdate_status(self, status, message):
        icon = self.icon[self.status_list.index(self.sdwdate_status)]
        self.sdwdate_status = status
        self.sdwdate_message = message
        self.update_menu()
        self.update_tip('sdwdate')
        self.set_tray_icon()

    def parse_tor_status(self):
        if self.tor_status == '':
            return

        if self.tor_status == 'running':
            self.tor_message = 'Tor is running.'

        elif self.tor_status == 'disabled':
            self.tor_message = '<b>Tor is disabled</b>. Therefore you most likely<br> \
            can not connect to the internet. <br><br> \
            Run <b>Anon Connection Wizard</b> from the menu'

        elif self.tor_status == 'stopped':
            self.tor_message = '<b>Tor is not running.</b> <br><br> \
            You have to fix this error, before you can use Tor. <br> \
            Please restart Tor after fixing this error. <br><br> \
            Start Menu -> System -> Restart Tor GUI<br> \
            or in Terminal: <br> \
            sudo service tor@default restart <br><br> '

        elif self.tor_status == 'disabled-running':
            self.tor_message = '<b>Tor is running but is disabled.</b><br><br> \
            A line <i>DisableNetwork 1</i> exists in torrc <br> \
            Run <b>Anon Connection Wizard</b> from the menu <br>\
            to connect to or configure the Tor network.'

        self.update_tip('tor')
        self.update_menu()
        self.set_tray_icon()

    def status_changed(self):
        try:
            with open(self.status_path, 'r') as f:
                status = json.load(f)
        except:
            error_msg = "status_changed unexpected error: " + str(sys.exc_info()[0])
            print(error_msg)
            return

        self.parse_sdwdate_status(status['icon'], status['message'])

    def tor_status_changed(self):
        if not anon_connection_wizard_installed:
            ## tor_status() unavailable.
            return

        try:
            tor_is_enabled = tor_status.tor_status() == 'tor_enabled'
            tor_is_running = os.path.exists(self.tor_running_path)
        except:
            error_msg = "tor_status_changed unexpected error: " + str(sys.exc_info()[0])
            print(error_msg)
            return

        if tor_is_enabled and tor_is_running:
            self.tor_status = 'running'
        elif not tor_is_enabled:
            if tor_is_running:
                self.tor_status =  'disabled-running'
            elif not tor_is_running:
                self.tor_status =  'disabled'
        elif not tor_is_running:
            self.tor_status =  'stopped'

        self.parse_tor_status()

    def show_tor_status(self):
        command = 'tor-control-panel &'
        subprocess.Popen(command.split())

    def show_sdwdate_log(self):
        command = ('/usr/libexec/sdwdate-gui/log-viewer &')
        subprocess.Popen(command.split())

    def restart_sdwdate(self):
        command = 'sudo --non-interactive /usr/sbin/sdwdate-clock-jump'
        subprocess.Popen(command.split())

    def stop_sdwdate(self):
        if self.tor_status == 'running':
            command = 'sudo --non-interactive systemctl --no-pager --no-block stop sdwdate'
            subprocess.Popen(command.split())

def signal_handler(sig, frame):
    sys.exit(0)

def main():
    app = QtWidgets.QApplication(["Sdwdate"])

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    timer = QtCore.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    sdwdate_tray = SdwdateTrayIcon()
    sdwdate_tray.show()
    app.exec_()

if __name__ == "__main__":
    main()
