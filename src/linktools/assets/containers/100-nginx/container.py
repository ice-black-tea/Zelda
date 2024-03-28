#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@author  : Hu Ji
@file    : deploy.py 
@time    : 2023/05/21
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
import re
import shutil

from linktools import Config, utils
from linktools.container import BaseContainer
from linktools.decorator import cached_property


class Container(BaseContainer):

    @cached_property
    def keys(self):
        # dnsapi.txt 内容从 https://github.com/acmesh-official/acme.sh/wiki/dnsapi 拷贝
        with open(os.path.join(os.path.dirname(__file__), "dnsapi.txt"), "rt") as fd:
            pattern = re.compile(r'export +(\w+)="?')
            return sorted(list(set(pattern.findall(fd.read()))))

    @cached_property
    def configs(self):
        return dict(
            ROOT_DOMAIN=Config.Prompt(cached=True),
            WILDCARD_DOMAIN=Config.Confirm(default=False, cached=True),
            HTTP_PORT=Config.Prompt(default=80, type=int, cached=True),
            HTTPS_PORT=Config.Prompt(default=443, type=int, cached=True),
            ACME_DNS_API=Config.Sample({
                "ACME_DNS_API": "dns_ali  <= parameter --dns, find from https://github.com/acmesh-official/acme.sh/wiki/dnsapi",
                "Ali_Key     ": "<key>    <= environment variable with dns_ali",
                "Ali_Secret  ": "<secret> <= environment variable with dns_ali",
            })
        )

    @cached_property
    def enable(self):
        return self.manager.config.get(
            "NGINX_ENABLE",
            type=bool,
            default=Config.Confirm(default=True, cached=True)
        )

    def on_starting(self):
        path = self.get_app_path("conf.d")
        if not os.path.exists(path):
            return
        for name in os.listdir(path):
            target_path = os.path.join(path, name)
            if os.path.isdir(target_path):
                shutil.rmtree(target_path, ignore_errors=True)
            else:
                utils.ignore_error(os.remove, args=(target_path,))

    def on_started(self):
        self.manager.change_owner(
            self.get_app_path(),
            self.manager.user
        )
