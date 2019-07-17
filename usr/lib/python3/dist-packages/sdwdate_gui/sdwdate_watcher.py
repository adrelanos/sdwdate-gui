#!/usr/bin/python3 -u

## Copyright (C) 2015 - 2017 ENCRYPTED SUPPORT LP <adrelanos@riseup.net>
## See the file COPYING for copying conditions.

import sys
from PyQt5 import QtWidgets
from PyQt5.QtCore import QFileSystemWatcher
from subprocess import call, check_output
import json

import signal
signal.signal(signal.SIGINT, signal.SIG_DFL)


class SdwdateStatusWatch:
    def __init__(self, parent=None):
        try:
            self.name = check_output(['qubesdb-read', '/name']).decode().strip()
            #if self.name.startswith('disp'):
                #sys.exit(0)
        except:
            print(str(sys.exc_info()[0]))
            self.name = 'name'

        self.status_path = '/var/run/sdwdate/status'

        ## get status on loading.
        self.status_changed()

        self.watcher_file = QFileSystemWatcher([self.status_path])
        self.watcher_file.fileChanged.connect(self.status_changed)

    def status_changed(self):
        try:
            with open(self.status_path, 'r') as f:
                status = json.load(f)
                f.close()
        except:
            error_msg = "Unexpected error: " + str(sys.exc_info()[0])
            print(error_msg)
            return

        try:
            ## in case qubes-qrexec-agent is not running.
            command = 'qrexec-client-vm sys-whonix whonix.NewStatus+"%s"' % (self.name)
            call(command, shell=True)
        except:
            pass


def main():
    app = QtWidgets.QApplication(["Sdwdate"])
    watcher = SdwdateStatusWatch()
    app.exec_()

if __name__ == "__main__":
    main()
