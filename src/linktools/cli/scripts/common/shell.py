#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import getpass
import os
import pwd
import shutil
from argparse import ArgumentParser
from typing import Optional

from linktools import utils, tools
from linktools.cli import ConsoleScript


class Script(ConsoleScript):
    """
    Shell with environment variables already initialized
    """

    def __init__(self):
        self._shell_path = None
        if tools.system in ["darwin", "linux"]:
            try:
                self._shell_path = pwd.getpwnam(getpass.getuser()).pw_shell
            except:
                self._shell_path = shutil.which("bash") or shutil.which("sh")
            if "SHELL" in os.environ:
                self._shell_path = os.environ["SHELL"]
        elif tools.system in ["windows"]:
            self._shell_path = shutil.which("powershell") or shutil.which("cmd")
            if "ComSpec" in os.environ:
                self._shell_path = os.environ["ComSpec"]

    def _add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("-c", "--command", action="store", default=None, help="shell command")

    def _run(self, args: [str]) -> Optional[int]:
        args = self.argument_parser.parse_args()
        if args.command:
            process = utils.Popen(args.command, shell=True)
            return process.call()

        if not os.path.exists(self._shell_path):
            raise NotImplementedError(f"unsupported system {tools.system}")

        process = utils.Popen(self._shell_path)
        return process.call()


script = Script()
if __name__ == "__main__":
    script.main()