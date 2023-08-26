#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@author  : Hu Ji
@file    : at_frida.py
@time    : 2018/11/25
@site    :
@software: PyCharm

              ,----------------,              ,---------,
         ,-----------------------,          ,"        ,"|
       ,"                      ,"|        ,"        ,"  |
      +-----------------------+  |      ,"        ,"    |
      |  .-----------------.  |  |     +---------+      |
      |  |                 |  |  |     | -==----'|      |
      |  | $ sudo rm -rf / |  |  |     |         |      |
      |  |                 |  |  |/----|`---=    |      |
      |  |                 |  |  |   ,/|==== ooo |      ;
      |  |                 |  |  |  // |(((( [33]|    ,"
      |  `-----------------'  |," .;'| |((((     |  ,"
      +-----------------------+  ;;  | |         |,"
         /_)______________(_/  //'   | +---------+
    ___________________________/___  `,
   /  oooooooooooooooo  .o.  oooo /,   \,"-----------
  / ==ooooooooooooooo==.o.  ooo= //   ,`\--{)B     ,"
 /_==__==========__==_ooo__ooo=_/'   /___________,"
"""
import re
from argparse import ArgumentParser
from typing import Optional

from linktools import utils, environ
from linktools.cli.argparse import KeyValueAction
from linktools.cli.ios import IOSCommand
from linktools.frida import FridaApplication, FridaShareScript, FridaScriptFile, FridaEvalCode
from linktools.frida.ios import IOSFridaServer


class Command(IOSCommand):
    """
    Easy to use frida (require iOS device jailbreak)
    """

    def init_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("-b", "--bundle-id", action="store", default=None,
                            help="target bundle id (default: frontmost application)")
        parser.add_argument("--spawn", action="store_true", default=False,
                            help="inject after spawn (default: false)")

        parser.add_argument("-P", "--parameters",
                            action=KeyValueAction, nargs="+", dest="user_parameters", default={},
                            help="user script parameters")

        parser.add_argument("-l", "--load", metavar="SCRIPT",
                            action="append", dest="user_scripts", default=[],
                            type=lambda o: FridaScriptFile(o),
                            help="load user script")
        parser.add_argument("-e", "--eval", metavar="CODE", action="append", dest="user_scripts",
                            type=lambda o: FridaEvalCode(o),
                            help="evaluate code")
        parser.add_argument("-c", "--codeshare", metavar="URL", action="append", dest="user_scripts",
                            type=lambda o: FridaShareScript(o, cached=False),
                            help="load share script url")

        parser.add_argument("-a", "--auto-start", action="store_true", default=False,
                            help="automatically start when all processes exits")

    def run(self, args: [str]) -> Optional[int]:
        args = self.parse_args(args)

        user_parameters = args.user_parameters
        user_scripts = args.user_scripts

        device = args.parse_device()
        bundle_id = args.bundle_id

        class Application(FridaApplication):

            def on_session_detached(self, session, reason, crash) -> None:
                environ.logger.info(f"{session} detached, reason={reason}")
                if reason in ("connection-terminated", "device-lost"):
                    self.stop()
                elif len(self.sessions) == 0:
                    if args.auto_start:
                        app.load_script(app.device.spawn(bundle_id), resume=True)

        with IOSFridaServer(device=device, local_port=utils.pick_unused_port()) as server:

            # 如果没有填包名，则找到顶层应用
            if utils.is_empty(bundle_id):
                target_app = server.get_frontmost_application()
                if target_app is None:
                    environ.logger.error("Unknown frontmost application")
                    return
                bundle_id = target_app.identifier

            app = Application(
                server,
                target_identifiers=rf"^{re.escape(bundle_id)}$",
                user_parameters=user_parameters,
                user_scripts=user_scripts,
                enable_spawn_gating=True
            )

            if args.spawn:
                # 打开进程后注入
                app.load_script(app.device.spawn(bundle_id), resume=True)

            elif app.inject_all():
                # 注入所有进程进程
                pass

            elif args.auto_start:
                # 进程不存在，打开进程后注入
                app.load_script(app.device.spawn(bundle_id), resume=True)

            app.run()


command = Command()
if __name__ == "__main__":
    command.main()
