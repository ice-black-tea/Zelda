#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@author  : Hu Ji
@file    : resource.py 
@time    : 2018/12/01
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

from .decorator import cached_property


class Resource(object):

    def get_persist_path(self, *paths: [str]):
        return self._get_path(self._resource_path, *paths, create=False, create_parent=False)

    def get_data_path(self, *paths: [str], create_parent: bool = False):
        return self._get_path(self._data_path, *paths, create=False, create_parent=create_parent)

    def get_data_dir(self, *paths: [str], create: bool = False):
        return self._get_path(self._data_path, *paths, create=create, create_parent=False)

    def get_temp_path(self, *paths: [str], create_parent: bool = False):
        return self._get_path(self._temp_path, *paths, create=False, create_parent=create_parent)

    def get_temp_dir(self, *paths: [str], create: bool = False):
        return self._get_path(self._temp_path, *paths, create=create, create_parent=False)

    @cached_property
    def _resource_path(self):
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "resource"))

    @cached_property
    def _data_path(self):
        from . import config
        path = config["SETTING_DATA_PATH"]
        if path is None or len(path) == 0:
            path = os.path.join(config["SETTING_STORAGE_PATH"], "data")
        return path

    @cached_property
    def _temp_path(self):
        from . import config
        path = config["SETTING_TEMP_PATH"]
        if path is None or len(path) == 0:
            path = os.path.join(config["SETTING_STORAGE_PATH"], "temp")
        return path

    @classmethod
    def _get_path(cls, root_path: str, *paths: [str], create: bool = False, create_parent: bool = False):
        path = os.path.join(root_path, *paths)
        dir_path = None
        if create:
            dir_path = path
        elif create_parent:
            dir_path = os.path.dirname(path)
        if dir_path is not None:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
        return path
