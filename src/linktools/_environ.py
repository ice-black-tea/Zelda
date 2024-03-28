#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@author  : Hu Ji
@file    : environment.py
@time    : 2020/03/01
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
import abc
import getpass
import json
import logging
import os
import pathlib
from typing import TYPE_CHECKING, TypeVar, Type, Any

from . import utils, metadata
from .decorator import cached_property, cached_classproperty

if TYPE_CHECKING:
    from ._config import ConfigDict, Config
    from ._tools import Tools, Tool
    from ._url import UrlFile

    T = TypeVar("T")

root_path = os.path.dirname(__file__)
asset_path = os.path.join(root_path, "assets")


class BaseEnviron(abc.ABC):

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """
        模块名
        """
        pass

    @property
    def version(self) -> str:
        """
        模块版本号
        """
        return NotImplemented

    @property
    def description(self) -> str:
        """
        模块描述
        """
        return NotImplemented

    @property
    def root_path(self) -> str:
        """
        模块路径
        """
        raise NotImplemented

    @property
    def system(self) -> str:
        """
        系统名称
        """
        return self.tools.system

    @property
    def machine(self) -> str:
        """
        机器类型，e.g. 'i386'
        """
        return self.tools.machine

    @property
    def debug(self) -> bool:
        """
        debug模式
        """
        return self.get_config("DEBUG", type=bool, default=False)

    @debug.setter
    def debug(self, value: bool) -> None:
        """
        debug模式
        """
        self.set_config("DEBUG", value)

    @cached_property
    def data_path(self) -> str:
        """
        存放文件目录
        """
        prefix = f"{metadata.__name__}_".upper()
        path = os.environ.get(f"{prefix}_DATA_PATH", None)
        if path:  # 优先使用环境变量中的${DATA_PATH}
            return path
        path = os.environ.get(f"{prefix}_STORAGE_PATH", None)
        if path:  # 其次使用环境变量中的${STORAGE_PATH}/data
            return os.path.join(path, "data")
        # 最后使用默认路径${HOME}/.linktools/data
        return os.path.join(str(pathlib.Path.home()), f".{metadata.__name__}", "data")

    @cached_property
    def temp_path(self) -> str:
        """
        存放临时文件目录
        """
        prefix = f"{metadata.__name__}_".upper()
        path = os.environ.get(f"{prefix}_TEMP_PATH", None)
        if path:  # 优先使用环境变量中的${TEMP_PATH}
            return path
        path = os.environ.get(f"{prefix}_STORAGE_PATH", None)
        if path:  # 其次使用环境变量中的${STORAGE_PATH}/temp
            return os.path.join(path, "temp")
        # 最后使用默认路径${HOME}/.linktools/temp
        return os.path.join(str(pathlib.Path.home()), f".{metadata.__name__}", "temp")

    def get_path(self, *paths: str) -> str:
        """
        获取模块目录下的子路径
        """
        if self.root_path == NotImplemented:
            raise RuntimeError("root_path not implemented")
        return utils.get_path(self.root_path, *paths)

    def get_data_path(self, *paths: str, create_parent: bool = False) -> str:
        """
        获取数据目录下的子路径
        """
        return utils.get_path(self.data_path, *paths, create=False, create_parent=create_parent)

    def get_data_dir(self, *paths: str, create: bool = False) -> str:
        """
        获取数据目录下的子目录
        """
        return utils.get_path(self.data_path, *paths, create=create, create_parent=False)

    def get_temp_path(self, *paths: str, create_parent: bool = False) -> str:
        """
        获取临时文件目录下的子路径
        """
        return utils.get_path(self.temp_path, *paths, create=False, create_parent=create_parent)

    def get_temp_dir(self, *paths: str, create: bool = False) -> str:
        """
        获取临时文件目录下的子目录
        """
        return utils.get_path(self.temp_path, *paths, create=create, create_parent=False)

    @cached_classproperty
    def _log_manager(self) -> logging.Manager:

        empty_args = tuple()

        class Logger(logging.Logger):

            def _log(self, level, msg, args, **kwargs):
                msg = str(msg)
                msg += ''.join([str(i) for i in args])

                kwargs["extra"] = kwargs.get("extra") or {}
                self._move_args(
                    kwargs, kwargs["extra"],
                    "style", "indent", "markup", "highlighter"
                )

                return super()._log(level, msg, empty_args, **kwargs)

            @classmethod
            def _move_args(cls, from_, to_, *keys):
                for key in keys:
                    value = from_.pop(key, None)
                    if value is not None:
                        to_[key] = value

        class LogManager(utils.get_derived_type(logging.Manager)):

            def __init__(self, manager):
                super().__init__(manager)
                object.__setattr__(self, "loggerClass", Logger)

            def getLogger(self, name):
                return logging.Manager.getLogger(self, name)

        return LogManager(logging.root.manager)

    @cached_property
    def logger(self) -> logging.Logger:
        """
        模块根logger
        """
        return self._log_manager.getLogger(self.name)

    def get_logger(self, name: str = None) -> logging.Logger:
        """
        获取模块名作为前缀的logger
        """
        name = f"{self.name}.{name}" if name else self.name
        return self._log_manager.getLogger(name)

    @cached_classproperty
    def _default_config(self) -> "ConfigDict":
        from ._config import ConfigDict

        config = ConfigDict()

        yaml_path = os.path.join(root_path, "template", "tools.yml")
        if metadata.__release__ or not os.path.exists(yaml_path):
            config.update_from_file(
                os.path.join(asset_path, "tools.json"),
                json.load
            )
        else:
            import yaml
            config.update_from_file(
                yaml_path,
                yaml.safe_load
            )

        return config

    def _create_config(self) -> "Config":
        from ._config import Config

        return Config(self, self._default_config)

    @cached_property
    def config(self) -> "Config":
        """
        环境相关配置
        """
        config = self._create_config()
        config.load_from_env()
        return config

    def wrap_config(self) -> "Config":
        """
        环境相关配置，与environ.config共享数据
        """
        from ._config import ConfigWrapper

        return ConfigWrapper(self.config)

    def get_config(self, key: str, type: "Type[T]" = None, default: Any = metadata.__missing__) -> "T":
        """
        获取指定配置，优先会从环境变量中获取
        """
        return self.config.get(key=key, type=type, default=default)

    def set_config(self, key: str, value: Any) -> None:
        """
        更新配置
        """
        self.config.set(key, value)

    def _create_tools(self) -> "Tools":
        from ._tools import Tools

        tools = Tools(self)

        # set environment variable
        index = 0
        dir_names = os.environ["PATH"].split(os.pathsep)
        for tool in tools:
            # dirname(executable[0]) -> environ["PATH"]
            if tool.executable:
                dir_name = tool.dirname
                if dir_name and dir_name not in dir_names:
                    # insert to head
                    dir_names.insert(index, tool.dirname)
                    index += 1
        # add all paths to environment variables
        os.environ["PATH"] = os.pathsep.join(dir_names)

        return tools

    @cached_property
    def tools(self) -> "Tools":
        """
        工具集
        """
        return self._create_tools()

    def get_tool(self, name: str, **kwargs) -> "Tool":
        """
        获取指定工具
        """
        tool = self.tools[name]
        if len(kwargs) != 0:
            tool = tool.copy(**kwargs)
        return tool

    def get_url_file(self, url: str) -> "UrlFile":
        """
        获取指定url
        """
        from ._url import UrlFile

        return UrlFile(self, url)


class Environ(BaseEnviron):

    @property
    def name(self) -> str:
        return metadata.__name__

    @property
    def version(self) -> str:
        return metadata.__version__

    @property
    def description(self) -> str:
        return metadata.__description__

    @property
    def root_path(self) -> str:
        return root_path

    def _create_config(self):
        config = super()._create_config()

        # 初始化下载相关参数
        config.set(
            "DEFAULT_USER_AGENT",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 "
            "Safari/537.36"
        )

        # 导入configs文件夹中所有配置文件
        config.update_from_file(
            os.path.join(asset_path, "android-tools.json"),
            load=json.load
        )

        return config

    def get_asset_path(self, *paths: str) -> str:
        return utils.get_path(asset_path, *paths)


environ = Environ()
