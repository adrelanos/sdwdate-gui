#!/usr/bin/python3 -u

## Copyright (C) 2015 - 2017 Patrick Schleizer <adrelanos@riseup.net>
## See the file COPYING for copying conditions.

import sys
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QMenu, QAction
from PyQt5.QtCore import QFileSystemWatcher
from PyQt5.QtCore import QProcess
import subprocess
from subprocess import check_output, call, Popen, PIPE
import json
import os
import re

import signal
signal.signal(signal.SIGINT, signal.SIG_DFL)


class Update(QtCore.QObject):
    update_tip = QtCore.pyqtSignal()


class SdwdateTrayIcon(QtWidgets.QSystemTrayIcon):
    def __init__(self, parent=None):
        QtWidgets.QSystemTrayIcon.__init__(self, parent)

        self.title = 'Time Synchronisation Monitor'

        self.name = check_output(['qubesdb-read', '/name']).decode().strip()

        self.status_path = '/var/run/sdwdate/status'
        self.anon_status_path = '/var/run/sdwdate-gui/anon-status'
        self.show_message_path = '/usr/lib/sdwdate-gui/show_message'
        self.popup_process = None

        self.update = Update(self)
        self.update.update_tip.connect(self.update_tip)

        self.clicked_once = False
        self.pos_x = 0
        self.pos_y = 0

        self.domain_list = []
        self.domain_status_list = []
        self.domain_icon_list = []
        self.domain_message_list = []
        self.current_vm = ''

        self.icon = ['/usr/share/icons/sdwdate-gui/Ambox_currentevent.svg.png',
                     '/usr/share/icons/sdwdate-gui/620px-Ambox_outdated.svg.png',
                     '/usr/share/icons/sdwdate-gui/212px-Timeblock.svg.png']

        self.status = ['success', 'busy', 'error']

        self.domain_list.append(self.name)
        self.domain_status_list.append('busy')
        self.domain_icon_list.append(self.icon[self.status.index('busy')])
        self.domain_message_list.append('Waiting for first sdwdate status...')

        self.setIcon(QtGui.QIcon(self.icon[self.status.index('busy')]))

        self.setToolTip('Time Synchronisation Monitor \n Right-click for menu.')

        self.status_changed()

        self.anon_watcher_file = QFileSystemWatcher([self.anon_status_path])
        self.anon_watcher_file.fileChanged.connect(self.anon_vm_status_changed)

        self.watcher_file = QFileSystemWatcher([self.status_path])
        self.watcher_file.fileChanged.connect(self.status_changed)

        self.create_menu()


    def run_popup(self, vm):
        index = self.domain_list.index(vm)
        status = self.domain_message_list[index]

        popup_process_cmd = ('%s "%s" %s %s &'
                % (self.show_message_path, self.pos_x, self.pos_y, 'Domain<b> %s</b><br>%s' % (vm, status)))
        self.popup_process = QProcess()
        self.popup_process.start(popup_process_cmd)


    def show_message(self, vm):
        self.set_current_vm(vm)
        ## for sys-whonix
        if self.current_vm == self.name:
            vm = self.name

        ## Store own position for message gui.
        if not self.clicked_once:
            self.pos_x = QtGui.QCursor.pos().x() - 50
            self.pos_y = QtGui.QCursor.pos().y() - 50
            self.clicked_once = True

        if self.popup_process == None:
            self.run_popup(vm)
            return

        if self.popup_process.pid() > 0:
            try:
                  self.popup_process.kill()
            except:
                  pass
            self.popup_process = None
            self.run_popup(vm)
        else:
            self.run_popup(vm)


    def update_tip(self):
        if self.popup_process == None:
            return

        ## Update message only if already shown.
        if self.popup_process.pid() > 0:
            self.show_message(self.current_vm)


    def set_current_vm(self, vm):
        ''' for use in update_tip,
        '''
        self.current_vm = vm


    def create_menu(self):
        def create_sub_menu(menu):
            action = QtWidgets.QAction('Show status', self)
            action.triggered.connect(lambda: self.show_message(menu.title()))
            menu.addAction(action)

            menu.addSeparator()

            icon = QtGui.QIcon('/usr/share/icons/sdwdate-gui/text-x-script.png')
            action = QtWidgets.QAction(icon, "Open sdwdate's log", self)
            action.triggered.connect(lambda: show_log(menu.title()))
            menu.addAction(action)

            menu.addSeparator()

            icon = QtGui.QIcon('/usr/share/icons/sdwdate-gui/system-reboot.png')
            text = 'Restart sdwdate'
            action = QtWidgets.QAction(icon, text, self)
            action.triggered.connect(lambda: restart_sdwdate(menu.title()))
            menu.addAction(action)

            icon = QtGui.QIcon('/usr/share/icons/sdwdate-gui/system-shutdown.png')
            action = QtWidgets.QAction(icon, "Stop sdwdate", self)
            action.triggered.connect(lambda: stop_sdwdate(menu.title()))
            menu.addAction(action)

        menu = QMenu()

        for vm in self.domain_list:
            icon = QtGui.QIcon(self.domain_icon_list[self.domain_list.index(vm)])
            menu_item = menu.addMenu(icon, vm)
            if vm == self.name:
                menu.addSeparator()
            create_sub_menu(menu_item)

        #menu.addSeparator()

        #icon = QtGui.QIcon('/usr/share/icons/sdwdate-gui/application-exit.png')
        #action = QAction(icon, "&Exit", self)
        #action.triggered.connect(sys.exit)
        #menu.addAction(action)

        self.setContextMenu(menu)


    def set_tray_icon(self):
        status_index = 0

        for status in self.domain_status_list:
            if self.status.index(status) > status_index:
                status_index = self.status.index(status)

        self.setIcon(QtGui.QIcon(self.icon[status_index]))


    def remove_vm(self, vm):
        name = vm.rsplit('_', 1)[0]
        if name in self.domain_list:
            index = self.domain_list.index(name)

            self.domain_list.pop(index)
            self.domain_status_list.pop(index)
            self.domain_icon_list.pop(index)
            self.domain_message_list.pop(index)

            self.create_menu()
            self.set_tray_icon()


    def parse_status(self, vm, status, message):
        icon = self.icon[self.status.index(status)]

        if vm not in self.domain_list:
            self.domain_list.append(vm)
            self.domain_status_list.append(status)
            self.domain_icon_list.append(icon)
            self.domain_message_list.append(message)
        else:
            index = self.domain_list.index(vm)
            self.domain_status_list[index] = status
            self.domain_icon_list[index] = icon
            self.domain_message_list[index] = message

        self.update.update_tip.emit()
        self.create_menu()
        self.set_tray_icon()


    def anon_vm_status_changed(self):
        with open(self.anon_status_path, 'r') as f:
            vm_name = f.read().strip()

        if not vm_name == '':
            if  vm_name.endswith('shutdown'):
                self.remove_vm(vm_name)
            else:
                try:
                    command = ['qrexec-client-vm', vm_name, 'whonix.SdwdateStatus']
                    p = Popen(command, stdout=PIPE, stderr=PIPE)
                    stdout, stderr = p.communicate()
                    status = json.loads(stdout.decode())
                except:
                    error_msg = "Unexpected error: " + str(sys.exc_info()[0])
                    print(error_msg)
                    return

                self.parse_status(vm_name, status['icon'], status['message'])


    def status_changed(self):
        ## json.load(f) could fail if self.status_path,
        ## - is still empty (sdwdate has not been started yet)
        ## - contains invalid contents (if sdwdate got killed the moment it was
        ##   writing to that file.
        ## - status is None. Probably introduced by QFileSystemWatcher.
        try:
            with open(self.status_path, 'r') as f:
                status = json.load(f)
        except:
            error_msg = "Unexpected error: " + str(sys.exc_info()[0])
            print(error_msg)
            return

        self.parse_status(self.name, status['icon'], status['message'])


def show_log(vm):
    t = SdwdateTrayIcon()
    if vm == t.name:
        show_konsole = ('konsole --hold -e "tail -f -n 100 /var/log/sdwdate.log"')
        Popen(show_konsole, shell=True)
    else:
        command = 'qrexec-client-vm %s whonix.GatewayCommand+"showlog" &' % vm
        call(command, shell=True)


def restart_sdwdate(vm):
    t = SdwdateTrayIcon()
    if vm == t.name:
        if os.path.exists('/var/run/sdwdate/success'):
            Popen('sudo --non-interactive rm /var/run/sdwdate/success', shell=True)
        Popen('sudo --non-interactive systemctl --no-pager --no-block restart sdwdate', shell=True)
    else:
        command = 'qrexec-client-vm %s whonix.GatewayCommand+"restart" &' % vm
        call(command, shell=True)


def stop_sdwdate(vm):
    t = SdwdateTrayIcon()
    if vm == t.name:
        Popen('sudo --non-interactive systemctl --no-pager --no-block stop sdwdate', shell=True)
    else:
        command = 'qrexec-client-vm %s whonix.GatewayCommand+"stop" &' % vm
        call(command, shell=True)


def main():
    app = QtWidgets.QApplication(["Sdwdate"])
    sdwdate_tray = SdwdateTrayIcon()
    sdwdate_tray.show()
    app.exec_()

if __name__ == "__main__":
    main()
