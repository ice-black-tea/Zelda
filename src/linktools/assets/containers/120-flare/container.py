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

import yaml

from linktools import Config
from linktools.container import BaseContainer
from linktools.container.container import ExposeMixin, ExposeLink, ExposeCategory
from linktools.decorator import cached_property


class Container(BaseContainer):

    @property
    def dependencies(self) -> [str]:
        return ["nginx"]

    @cached_property
    def configs(self):
        return dict(
            WILDCARD_DOMAIN=True,

            FLARE_DISABLE_LOGIN=Config.Confirm(default=True, cached=True),
            FLARE_DOAMIN=self.get_nginx_domain(""),
            FLARE_EXPOSE_PORT=None,
            FLARE_USER=Config.Prompt(default="admin", cached=True),
            FLARE_PASSWORD=Config.Prompt(cached=True),
        )

    @cached_property
    def exposes(self) -> [ExposeLink]:
        return [
            self.expose_other("在线工具集合", "tools", "", "https://tool.lu/"),
            self.expose_other("在线正则表达式", "regex", "", "https://regex101.com/"),
            self.expose_other("正则表达式手册", "regex", "", "https://tool.oschina.net/uploads/apidocs/jquery/regexp.html"),
            self.expose_other("在线json解析", "codeJson", "", "https://www.json.cn/"),
            self.expose_other("DNS查询", "dns", "", "https://tool.chinaz.com/dns/"),
            self.expose_other("图标下载", "progressDownload", "", "https://materialdesignicons.com/"),
        ]

    def on_starting(self):

        categories = {}
        apps = []
        bookmarks = []

        for key, value in vars(ExposeMixin).items():
            if isinstance(value, ExposeCategory):
                categories.setdefault(value, list())

        for container in sorted(self.manager.containers.values(), key=lambda o: o.order):
            for expose in container.exposes:
                if isinstance(expose, ExposeLink) and expose.is_valid:
                    categories[expose.category].append(expose)
                    if expose.category is self.expose_public:
                        apps.append(expose)
                    bookmarks.append(expose)

        with open(self.get_app_path("app", "apps.yml", create_parent=True), "wt") as fd:
            data = {"links": []}
            for app in apps:
                data["links"].append({
                    "name": app.name,
                    "desc": app.desc,
                    "icon": app.icon,
                    "link": app.url,
                })
            yaml.dump(data, fd)

        with open(self.get_app_path("app", "bookmarks.yml", create_parent=True), "wt") as fd:
            data = {"categories": [], "links": []}
            for category, links in categories.items():
                if not links:
                    continue
                data["categories"].append({
                    "id": category.name,
                    "title": category.desc,
                })
                for link in links:
                    data["links"].append({
                        "category": category.name,
                        "name": link.name,
                        "icon": link.icon,
                        "link": link.url,
                    })
            yaml.dump(data, fd)

        self.manager.change_owner(
            self.get_app_path("app"),
            self.manager.config.get("DOCKER_USER"),
        )

        self.write_nginx_conf(
            self.manager.config.get("FLARE_DOAMIN"),
            self.get_path("nginx.conf"),
            name="flare",
        )
