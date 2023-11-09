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
import os
from argparse import ArgumentParser, Namespace
from typing import Optional

from rich import get_console
from rich.tree import Tree

from ._environ import environ
from .cli import BaseCommand, walk_commands
from .decorator import cached_property


class CategoryInfo:

    def __init__(self, name: str, prefix: str, description: str):
        self.name = name
        self.prefix = prefix
        self.description = description

    def __repr__(self):
        return self.name


class CommandInfo:

    def __init__(self, category: CategoryInfo, command: BaseCommand):
        self.category = category
        self.command = command

    @property
    def name(self):
        return self.command.name

    @property
    def description(self):
        return self.command.description

    def __repr__(self):
        return self.name


class Command(BaseCommand):
    module_path = environ.get_cli_path("commands")
    module_categories = (
        CategoryInfo(name="common", prefix="ct-", description="e.g. grep, shell, etc."),
        CategoryInfo(name="android", prefix="at-", description="e.g. adb, fastboot, etc."),
        CategoryInfo(name="ios", prefix="it-", description="e.g. sib, ssh, etc."),
    )

    @cached_property
    def commands(self):
        commands = {}
        for category in self.module_categories:
            commands[category] = []
            path = os.path.join(self.module_path, category.name)
            for command in walk_commands(path):
                commands[category].append(
                    CommandInfo(
                        category=category,
                        command=command,
                    )
                )
        return commands

    def init_arguments(self, parser: ArgumentParser) -> None:
        subparsers = parser.add_subparsers()
        for category, commands in self.commands.items():
            parser = subparsers.add_parser(
                category.name,
                help=category.description
            )
            parser.set_defaults(help=parser.print_help)
            catalog_subparsers = parser.add_subparsers()
            for command in commands:
                parser = catalog_subparsers.add_parser(
                    command.name,
                    parents=[command.command.argument_parser],
                    help=command.description,
                    add_help=False,
                )
                parser.set_defaults(func=command.command)

    def run(self, args: Namespace) -> Optional[int]:
        if hasattr(args, "func"):
            return args.func(args)
        elif hasattr(args, "help"):
            return args.help()

        tree = Tree("📎 All commands")
        for category, commands in self.commands.items():
            node = tree.add(f"📖 {category}")
            for command in commands:
                node.add(f"👉 {command.category.prefix}[bold red]{command.name}[/bold red]: {command.description}")

        console = get_console()
        if environ.description != NotImplemented:
            console.print(environ.description, highlight=False)
        console.print(tree, highlight=False)


command = Command()
if __name__ == '__main__':
    command.main()
