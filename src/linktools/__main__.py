#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@author  : Hu Ji
@file    : __main__.py 
@time    : 2022/12/13
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
from argparse import ArgumentParser
from typing import Optional

from rich import get_console
from rich.tree import Tree

from . import __description__, cli


class Command(cli.Command):

    @property
    def _commands(self):
        return cli.get_commands()

    def _add_arguments(self, parser: ArgumentParser) -> None:
        sub_parsers = parser.add_subparsers()
        for catalog in self._commands:
            parser = sub_parsers.add_parser(
                catalog.name,
                description=catalog.description
            )
            parser.set_defaults(help=parser.print_help)
            catalog_parser = parser.add_subparsers()
            for command in self._commands[catalog]:
                parser = catalog_parser.add_parser(
                    command.name,
                    help=command.description,
                    add_help=False,
                    prefix_chars=chr(0)
                )
                parser.add_argument("args", nargs="...")
                parser.set_defaults(func=command.command)

    def _run(self, args: [str]) -> Optional[int]:
        args = self.argument_parser.parse_args(args)
        if hasattr(args, "func") and hasattr(args, "args"):
            return args.func(args.args)
        elif hasattr(args, "help"):
            return args.help()

        tree = Tree("📎 All commands")
        for catalog in self._commands:
            node = tree.add(f"📖 {catalog}")
            for command in self._commands[catalog]:
                node.add(f"👉 {command.catalog.prefix}[bold red]{command.name}[/bold red]: {command.description}")

        console = get_console()
        console.print(__description__, highlight=False)
        console.print(tree, highlight=False)


command = Command()
if __name__ == '__main__':
    command.main()
