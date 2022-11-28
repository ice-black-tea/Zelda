#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@author  : Hu Ji
@file    : objection.py 
@time    : 2022/11/20
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

from linktools import utils, logger, resource, environ
from linktools.argparser.ios import IOSArgumentParser
from linktools.decorator import entry_point
from linktools.frida.ios import IOSFridaServer
from linktools.ios import MuxError


@entry_point(known_errors=(MuxError,))
def main():
    parser = IOSArgumentParser(description="easy to use frida")

    parser.add_argument("-b", "--bundle-id", action="store", default=None,
                        help="target bundle id (default: frontmost application)")
    parser.add_argument("-s", "--startup-command", action="append", default=[],
                        help="A command to run before the repl polls the device for information.")
    parser.add_argument("-c", "--file-commands", action="store",
                        help="A file containing objection commands, separated by a "
                             "newline, that will run before the repl polls the device for information.")
    parser.add_argument("-S", "--startup-script", action="store",
                        help="A script to import and run before the repl polls the device for information.")
    parser.add_argument("-P", "--plugin-folder", action="store", default=resource.get_asset_path("objection"),
                        help="The folder to load plugins from.")

    args = parser.parse_args()
    device = args.parse_device()

    with IOSFridaServer(device=device) as server:

        objection_args = ["objection"]
        if environ.debug:
            objection_args += ["--debug"]
        objection_args += ["-N", "-p", server.local_port]

        bundle_id = args.bundle_id
        if utils.is_empty(bundle_id):
            target_app = server.get_frontmost_application()
            if target_app is None:
                logger.error("Unknown frontmost application")
                return 1
            bundle_id = target_app.identifier
        objection_args += ["-g", bundle_id]
        objection_args += ["explore"]

        for command in args.startup_command:
            objection_args += ["--startup-command", command]
        if args.file_commands:
            objection_args += ["--file-commands", args.file_commands]
        if args.startup_script:
            objection_args += ["--startup-script", args.startup_script]
        if args.plugin_folder:
            objection_args += ["--plugin-folder", args.plugin_folder]

        return utils.Popen(*objection_args).call()


if __name__ == '__main__':
    main()