#!/usr/bin/python3 -u

## Copyright (C) 2015 - 2022 ENCRYPTED SUPPORT LP <adrelanos@whonix.org>
## See the file COPYING for copying conditions.

import sys
from PyQt5 import QtWidgets
from PyQt5.QtCore import QFileSystemWatcher
from subprocess import call, check_output
import json
import glob
import os
import re

import signal
signal.signal(signal.SIGINT, signal.SIG_DFL)


class SdwdateStatusWatch:
    def __init__(self, parent=None):
        self.status_path = '/run/sdwdate/status'

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
            error_msg = "Unexpected error during status_changed: " + str(sys.exc_info()[0])
            print(error_msg)
            return

        try:
            ## In case qubes-qrexec-agent is not running.

            ## Fallback.
            ## If gateway is not configured in config file, use default.
            ## Non-ideal.
            ## qrexec feature request: send this over qrexec to the NetVM I am connected to / sys-whonix hardcoded / sys-whonix unexpected autostart #5253
            ## https://github.com/QubesOS/qubes-issues/issues/5253
            ## Networks VMs are restarting themselves without valid reason #5930
            ## https://github.com/QubesOS/qubes-issues/issues/5930
            ## HARDCODED!
            gateway = "sys-whonix"

            if os.path.exists('/etc/sdwdate-gui.d/'):
                  files = sorted(glob.glob('/etc/sdwdate-gui.d/*.conf'))
                  for f in files:
                     with open(f) as conf:
                        lines = conf.readlines()
                     for line in lines:
                        if line.startswith('gateway'):
                              gateway = re.search(r'=(.*)', line).group(1)

            if os.path.exists('/usr/local/etc/sdwdate-gui.d/'):
                  files = sorted(glob.glob('/usr/local/etc/sdwdate-gui.d/*.conf'))
                  for f in files:
                     with open(f) as conf:
                        lines = conf.readlines()
                     for line in lines:
                        if line.startswith('gateway'):
                              gateway = re.search(r'=(.*)', line).group(1)

            command = 'qrexec-client-vm %s whonix.NewStatus+status' % (gateway)
            call(command, shell=True)
        except:
            pass


def main():
    app = QtWidgets.QApplication(["Sdwdate"])
    watcher = SdwdateStatusWatch()
    app.exec_()

if __name__ == "__main__":
    main()
