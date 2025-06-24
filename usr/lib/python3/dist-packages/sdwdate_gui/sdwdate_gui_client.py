#!/usr/bin/python3 -su

## Copyright (C) 2015 - 2025 ENCRYPTED SUPPORT LLC <adrelanos@whonix.org>
## See the file COPYING for copying conditions.

# pylint: disable=no-name-in-module,broad-exception-caught,import-error

"""
The client component of sdwdate-gui. Monitors sdwdate and Tor states, reports
these states to the server, and runs commands at the server's request.
"""

from __future__ import annotations

import signal
import os
import sys
import json
import subprocess
import re
import time
import logging

from types import FrameType
from typing import NoReturn, Pattern
from pathlib import Path

from PyQt5.QtCore import (
    QCoreApplication,
    QFileSystemWatcher,
    QTimer,
    QObject,
    pyqtSignal,
)
from PyQt5.QtNetwork import (
    QLocalSocket,
)


# pylint: disable=too-few-public-methods
class GlobalData:
    """
    Global data for sdwdate_gui_client.
    """

    sdwdate_gui_conf_dir: Path = Path("/etc/sdwdate-gui.d")
    anon_connection_wizard_installed: bool = False
    do_reconnect: bool = True
    monitor: SdwdateGuiMonitor | None = None


GlobalData.anon_connection_wizard_installed = os.path.exists(
    "/usr/bin/anon-connection-wizard"
)
if GlobalData.anon_connection_wizard_installed:
    from anon_connection_wizard import tor_status


def running_in_qubes_os() -> bool:
    """
    Detects if the server is running on Qubes OS. The behavior when getting
    the client's name has to be somewhat different on Qubes OS, so we need to
    adjust for that use case.
    """

    if Path("/usr/share/qubes/marker-vm").is_file():
        return True

    return False


def check_bytes_printable(buf: bytes) -> bool:
    """
    Checks if all bytes in the provided buffer are printable ASCII.
    """

    for byte in buf:
        if byte < 0x20 or byte > 0x7E:
            return False

    return True


# pylint: disable=too-many-instance-attributes
class SdwdateGuiMonitor(QObject):
    """
    Keeps the server up-to-date about sdwdate and Tor status, and runs
    commands from the server.

    The following functions are provided by the client and can be called by
    the server:
    - open_tor_control_panel
    - open_sdwdate_log
    - restart_sdwdate
    - stop_sdwdate
    - suppress_client_reconnect

    The following functions are provided by the server and can be called by
    the client:
    - set_client_name <name>
    - set_sdwdate_status [success|busy|error] [message]
    - set_tor_status [running|stopped|disabled|disabled_running|absent]
    """

    serverDisconnected = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        """
        Connects to the server.
        """

        QObject.__init__(self, parent)

        # pylint: disable=invalid-name

        self.sdwdate_status_path: str = "/run/sdwdate/status"
        self.tor_path: str = "/run/tor"
        self.torrc_path: str = "/usr/local/etc/torrc.d"
        self.tor_running_path: str = "/run/tor/tor.pid"

        self.server_socket: QLocalSocket = QLocalSocket()
        uid_str: str = str(os.getuid())
        sdwdate_run_dir: Path = Path(f"/run/user/{uid_str}/sdwdate-gui")
        server_socket_path: Path = sdwdate_run_dir.joinpath("sdwdate-gui-server.socket")
        server_pid_path: Path = sdwdate_run_dir.joinpath("server_pid")
        while not server_socket_path.exists():
            time.sleep(0.1)
        self.server_socket.connectToServer(str(server_socket_path))
        self.server_socket.waitForConnected()
        if self.server_socket.state() != QLocalSocket.ConnectedState:
            logging.error("Could not connect to sdwdate-gui server!")
            self.serverDisconnected.emit()
            return

        if server_pid_path.is_file() or not running_in_qubes_os():
            ## We have to send our own blank qrexec header.
            while not self.server_socket.write(b"\0") == 1:
                if self.server_socket.state() != QLocalSocket.ConnectedState:
                    logging.error("sdwdate-gui server disconnected very quickly!")
                    self.serverDisconnected.emit()
                    return

            ## We also have to set our own name.
            if running_in_qubes_os():
                client_name: str = subprocess.run(
                    [
                        "qubesdb-read",
                        "/name"
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                    encoding="utf-8",
                ).stdout.strip()
                if client_name == "":
                    client_name = os.uname()[1]
            else:
                client_name = os.uname()[1]
            self.__set_client_name(client_name)

        self.__sock_buf: bytes = b""

        if not GlobalData.anon_connection_wizard_installed:
            self.__set_tor_status("absent")
        else:
            self.tor_watcher = QFileSystemWatcher(
                [self.tor_path, self.torrc_path],
            )
            self.tor_watcher.directoryChanged.connect(self.tor_status_changed)
            self.tor_status_changed()

        ## TODO: wait until file self.status_path is created
        self.sdwdate_watcher = QFileSystemWatcher([self.sdwdate_status_path])
        self.sdwdate_watcher.fileChanged.connect(self.sdwdate_status_changed)
        self.sdwdate_status_changed()

        self.server_socket.readyRead.connect(self.__handle_incoming_data)
        self.server_socket.disconnected.connect(self.__handle_disconnect)

    def kick_server(self) -> None:
        """
        Forcibly disconnects the server from the client. Used as a
        security measure when the server sends invalid data to the client.
        """

        logging.error("Server sent invalid data. Disconnecting and exiting.")
        self.server_socket.disconnectFromServer()
        self.server_socket.waitForDisconnected()
        self.serverDisconnected.emit()

    def __try_parse_commands(self) -> None:
        """
        Tries to run any commands in the buffer.
        """

        while len(self.__sock_buf) >= 2:
            msg_len: int = int.from_bytes(
                self.__sock_buf[:2], byteorder="big", signed=False
            )
            self.__sock_buf = self.__sock_buf[2:]

            if msg_len == 0:
                continue
            if msg_len > len(self.__sock_buf):
                continue

            msg_buf: bytes = self.__sock_buf[:msg_len]
            self.__sock_buf = self.__sock_buf[msg_len:]

            if not check_bytes_printable(msg_buf):
                self.kick_server()
                return

            msg_string: str = msg_buf.decode(encoding="ascii")
            msg_parts: list[str] = msg_string.split(" ")
            if len(msg_parts) < 1:
                continue
            function_name = msg_parts[0]

            match function_name:
                case "open_tor_control_panel":
                    if len(msg_parts) != 1:
                        self.kick_server()
                        return
                    self.__open_tor_control_panel()
                case "open_sdwdate_log":
                    if len(msg_parts) != 1:
                        self.kick_server()
                        return
                    self.__open_sdwdate_log()
                case "restart_sdwdate":
                    if len(msg_parts) != 1:
                        self.kick_server()
                        return
                    self.__restart_sdwdate()
                case "stop_sdwdate":
                    if len(msg_parts) != 1:
                        self.kick_server()
                        return
                    self.__stop_sdwdate()
                case "suppress_client_reconnect":
                    if len(msg_parts) != 1:
                        self.kick_server()
                        return
                    self.__suppress_client_reconnect()

    def __handle_incoming_data(self) -> None:
        """
        Reads incoming data from the server into a buffer, parsing and running
        commands from the data.
        """

        self.__sock_buf += self.server_socket.readAll().data()
        self.__try_parse_commands()

    def __handle_disconnect(self) -> None:
        logging.warning("Server disconnected!")
        self.serverDisconnected.emit()

    ## SERVER-TO-CLIENT RPC CALLS
    @staticmethod
    def __open_tor_control_panel() -> None:
        # pylint: disable=consider-using-with
        subprocess.Popen(["/usr/bin/tor-control-panel"], shell=False)

    @staticmethod
    def __open_sdwdate_log() -> None:
        # pylint: disable=consider-using-with
        subprocess.Popen(["/usr/libexec/sdwdate-gui/log-viewer"], shell=False)

    @staticmethod
    def __restart_sdwdate() -> None:
        # pylint: disable=consider-using-with
        subprocess.Popen(["leaprun", "sdwdate-clock-jump"], shell=False)

    @staticmethod
    def __stop_sdwdate() -> None:
        # pylint: disable=consider-using-with
        subprocess.Popen(["leaprun", "stop-sdwdate"], shell=False)

    @staticmethod
    def __suppress_client_reconnect() -> None:
        GlobalData.do_reconnect = False

    ## CLIENT-TO-SERVER RPC CALLS
    def __generic_rpc_call(self, msg_bytes: bytes) -> None:
        """
        Sends an RPC call from the server to the client, following the wire
        format documented for this object.
        """

        if self.server_socket.state() != QLocalSocket.ConnectedState:
            return

        msg_len: int = len(msg_bytes)
        msg_buf: bytes = (
            msg_len.to_bytes(2, byteorder="big", signed=False) + msg_bytes
        )
        msg_len += 2
        while msg_len > 0:
            bytes_written: int = self.server_socket.write(
                msg_buf[len(msg_buf) - msg_len :]
            )
            msg_len -= bytes_written

    def __set_client_name(self, name: str) -> None:
        """
        RPC call from client to server. Sets the client's name on the
        server side.

        IMPORTANT: On non-Qubes systems, this data MUST be provided by the
        client itself, while on Qubes OS, this data MUST be provided by the
        qrexec subsystem. NOT provided by the client. If a client never
        sends a client name, the client will never appear in the GUI on
        non-Qubes systems, while if the client always sends a client name,
        the server will forcibly disconnect it under Qubes OS.
        """

        self.__generic_rpc_call(
            b"set_client_name " + name.encode(encoding="ascii")
        )

    def __set_sdwdate_status(self, status: str, msg: str) -> None:
        """
        RPC call from client to server. Updates the sdwdate status shown by
        the server.
        """

        # Encode spaces, newlines, and backslashes into octal escapes.
        msg_copy: str = msg.replace("\\", "\\134")
        msg_copy = msg_copy.replace(" ", "\\040")
        msg_copy = msg_copy.replace("\n", "\\012")

        self.__generic_rpc_call(
            b"set_sdwdate_status "
            + status.encode(encoding="ascii")
            + b" "
            + msg_copy.encode(encoding="ascii")
        )

    def __set_tor_status(self, status: str) -> None:
        """
        RPC call from client to server. Updates the sdwdate status shown by
        the server.
        """

        self.__generic_rpc_call(
            b"set_tor_status " + status.encode(encoding="ascii")
        )

    ## WATCHER EVENTS
    def sdwdate_status_changed(self) -> None:
        """
        Determine the current sdwdate status and send it to the server.
        """

        if not os.path.isfile(self.sdwdate_status_path):
            return

        try:
            with open(self.sdwdate_status_path, "r", encoding="utf-8") as f:
                status_dict: dict[str, str] = json.load(f)
        except json.decoder.JSONDecodeError as e:
            logging.warning("Could not parse JSON from sdwdate", exc_info=e)
            return
        except Exception as e:
            logging.error("Unexpected error", exc_info=e)
            return

        status_str: str = status_dict["icon"]
        message_str: str = status_dict["message"]
        if status_str in ("success", "busy", "error"):
            self.__set_sdwdate_status(status_str, message_str)
        else:
            logging.warning("Invalid data found in sdwdate status file!")

    def tor_status_changed(self) -> None:
        """
        Determine the current Tor status and send it to the server.
        """

        if not GlobalData.anon_connection_wizard_installed:
            ## tor_status() unavailable.
            return

        try:
            tor_is_enabled: bool = tor_status.tor_status() == "tor_enabled"
            tor_is_running: bool = os.path.exists(self.tor_running_path)
        except Exception as e:
            logging.error("Unexpected error", exc_info=e)
            return

        if tor_is_enabled and tor_is_running:
            self.__set_tor_status("running")
        elif not tor_is_enabled:
            if tor_is_running:
                self.__set_tor_status("disabled-running")
            else:
                self.__set_tor_status("disabled")
        else:
            self.__set_tor_status("stopped")


def try_reconnect_maybe() -> None:
    """
    Attempts to reconnect to the sdwdate-gui server if running on Qubes OS.
    Otherwise, terminates the client.
    """

    if not running_in_qubes_os() or not GlobalData.do_reconnect:
        sys.exit(0)

    time.sleep(1)
    GlobalData.monitor = SdwdateGuiMonitor()
    GlobalData.monitor.serverDisconnected.connect(try_reconnect_maybe)


def parse_config_file(config_file: str) -> None:
    """
    Parses a single config file.
    """

    comment_re: Pattern[str] = re.compile(".*#")
    with open(config_file, "r", encoding="utf-8") as f:
        for line in f:
            if comment_re.match(line):
                continue
            line = line.strip()
            if line == "":
                continue
            if not "=" in line:
                logging.error(
                    "Invalid line detected in file '%s'",
                    config_file,
                )
                sys.exit(1)
            line_parts: list[str] = line.split("=", maxsplit=1)
            config_key: str = line_parts[0]
            config_val: str = line_parts[1]
            match config_key:
                case "disable":
                    if config_val == "true":
                        sys.exit(0)
                    elif config_val == "false":
                        continue
                    else:
                        logging.error(
                            "Invalid value for 'disable' key detected "
                            "in file '%s'",
                            config_file,
                        )
                        sys.exit(1)
                case _:
                    continue


def parse_config_files() -> None:
    """
    Parses all config files under /etc/sdwdate-gui.d.
    """

    config_file_list: list[Path] = []
    if not GlobalData.sdwdate_gui_conf_dir.is_dir():
        logging.error(
            "'%s' is not a directory!",
            GlobalData.sdwdate_gui_conf_dir,
        )
        sys.exit(1)
    for config_file in GlobalData.sdwdate_gui_conf_dir.iterdir():
        if not config_file.is_file():
            continue
        config_file_list.append(config_file)
    config_file_list.sort()

    for config_file in config_file_list:
        parse_config_file(str(config_file))


# pylint: disable=unused-argument
def signal_handler(sig: int, frame: FrameType | None) -> None:
    """
    Handles SIGINT and SIGTERM.
    """

    sys.exit(128 + sig)


def main() -> NoReturn:
    """
    Main function.
    """

    if os.geteuid() == 0:
        print("ERROR: Do not run with sudo / as root!")
        sys.exit(1)

    if Path("/run/qubes/this-is-templatevm").is_file():
        print("INFO: Refusing to run in a QubesOS TemplateVM.")
        sys.exit(0)

    logging.basicConfig(
        format="%(funcName)s: %(levelname)s: %(message)s", level=logging.INFO
    )

    app: QCoreApplication = QCoreApplication(["Sdwdate"])

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    parse_config_files()

    timer: QTimer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    # pylint: disable=unused-variable
    GlobalData.monitor = SdwdateGuiMonitor()
    GlobalData.monitor.serverDisconnected.connect(try_reconnect_maybe)

    app.exec_()
    sys.exit(0)


if __name__ == "__main__":
    main()
