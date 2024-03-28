#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@author  : Hu Ji
@file    : tools.py
@time    : 2018/12/11
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
import pickle
import shutil
import sys
import warnings
from typing import TYPE_CHECKING, Dict, Union, Mapping, Iterator, Any, Tuple, List, Type

from . import utils
from .decorator import cached_property
from .metadata import __missing__

if TYPE_CHECKING:
    from ._environ import BaseEnviron


class Parser(object):

    def __init__(self, *items):
        self._conditions = tuple(self._get_condition(item) for item in items)

    def parse(self, cfg: Dict):
        result = {}
        for key in cfg:
            result[key] = self._extend_field(cfg, key)
        return result

    def _extend_field(self, cfg, key: str, default=None):
        value = utils.get_item(cfg, key, default=default)
        if isinstance(value, dict) and "case" in value:
            # parse case block:
            # -----------------------------------------
            #   field:
            #     case:                                 <== case_block
            #       - when: {system: [darwin, linux]}
            #         then: xxx
            #       - when: {system: windows}
            #         then: yyy
            #       - else: ~
            # -----------------------------------------
            case_block = value.get("case")

            for cond_block in case_block:

                when_block = utils.get_item(cond_block, "when")
                if when_block is not None:
                    # if it is a "when" block, verify it
                    # -----------------------------------------
                    #   field:
                    #     case:
                    #       - when: {system: [darwin, linux]}   <== when_block
                    #         then: xxx
                    #       - when: {system: windows}
                    #         then: yyy
                    #       - else: ~
                    # -----------------------------------------
                    is_verified = True
                    for condition in self._conditions:
                        if not condition(cfg, when_block):
                            is_verified = False
                            break

                    # if any one of the verification fails, skip
                    if not is_verified:
                        continue

                    # all items are verified, return "then"
                    # -----------------------------------------
                    #   field:
                    #     case:
                    #       - when: {system: [darwin, linux]}
                    #         then: xxx                         <== then_block
                    #       - when: {system: windows}
                    #         then: yyy
                    #       - else: ~
                    # -----------------------------------------
                    return utils.get_item(cond_block, "then", default=default)  # ==> find "case" "when" "then"

                else_block = utils.get_item(cond_block, "else")
                if else_block is not None:  # ==> find "case" => "else"
                    # if it is an else block, return "else"
                    # -----------------------------------------
                    #   field:
                    #     case:
                    #       - when: {system: [darwin, linux]}
                    #         then: xxx
                    #       - when: {system: windows}
                    #         then: yyy
                    #       - else: ~                           <== else_block
                    # -----------------------------------------
                    return else_block

            # use default value
            return default  # ==> not found "else"

        # use config value
        return value  # ==> not found "case"

    @classmethod
    def _get_condition(cls, item: str):

        def check(config, when_block):
            when_scope = utils.get_item(when_block, item)
            if when_scope is not None:
                # -----------------------------------------
                #   field:
                #     case:
                #       - when: {system: [darwin, linux]}   <== when_scope (system: [darwin, linux])
                #         then: xxx
                #       - when: {system: windows}
                #         then: yyy
                #       - else: ~
                # -----------------------------------------
                value = config[item]
                if isinstance(when_scope, str):
                    if value != when_scope:
                        return False
                elif isinstance(when_scope, (tuple, list, set)):
                    if value not in when_scope:
                        return False
            return True

        return check


class ToolProperty(object):

    def __init__(self, name=None, default=None):
        self.name = name
        self.default = default


class ToolMeta(type):

    def __new__(mcs, name, bases, attrs):
        # initialize __parser__
        attrs["__parser__"] = Parser("system", "machine")
        # initialize __default__
        attrs["__default__"] = {}
        for key in list(attrs.keys()):
            if isinstance(attrs[key], ToolProperty):
                var = attrs[key]
                var_name = var.name or key
                attrs["__default__"][var_name] = var.default
                attrs[key] = property(mcs.make_fget(var_name))
        return type.__new__(mcs, name, bases, attrs)

    @classmethod
    def make_fget(mcs, key):
        return lambda self: self.config.get(key)


class ToolError(Exception):
    pass


class ToolNotFound(ToolError):
    pass


class ToolExecError(ToolError):
    pass


class Tool(metaclass=ToolMeta):
    __default__: Dict
    __parser__: Parser

    name: str = ToolProperty(default=__missing__)
    depends_on: tuple = ToolProperty(default=[])
    download_url: str = ToolProperty(default=__missing__)
    target_path: bool = ToolProperty(default=__missing__)
    root_path: str = ToolProperty(default=__missing__)
    unpack_path: str = ToolProperty(default=__missing__)
    absolute_path: str = ToolProperty(default=__missing__)
    cmdline: str = ToolProperty(default=__missing__)
    executable: bool = ToolProperty(default=True)
    executable_cmdline: tuple = ToolProperty(default=[])

    exists: bool = property(lambda self: self.absolute_path and os.path.exists(self.absolute_path))
    dirname: bool = property(lambda self: None if not self.absolute_path else os.path.dirname(self.absolute_path))

    def __init__(self, container: "Tools", config: Union[dict, str], **kwargs):
        self._container = container
        self._config = config

        self._raw_config = pickle.loads(pickle.dumps(self.__default__))
        self._raw_config.update(container.config)
        self._raw_config.update(config)
        self._raw_config.update(kwargs)

    @cached_property
    def config(self) -> dict:
        cfg = self.__parser__.parse(self._raw_config)

        depends_on = utils.get_item(cfg, "depends_on")
        if depends_on:
            assert isinstance(depends_on, (str, Tuple, List)), \
                f"Tool<{cfg['name']}>.depends_on type error, " \
                f"str/tuple/list was expects, got {type(depends_on)}"
            if isinstance(depends_on, str):
                depends_on = [depends_on]
            for dependency in depends_on:
                assert dependency in self._container.items, \
                    f"Tool<{cfg['name']}>.depends_on error: not found Tool<{dependency}>"
            cfg["depends_on"] = depends_on

        # download url
        download_url = utils.get_item(cfg, "download_url") or ""
        if download_url is __missing__:
            download_url = ""
        assert isinstance(download_url, str), \
            f"Tool<{cfg['name']}>.download_url type error, " \
            f"str was expects, got {type(download_url)}"
        cfg["download_url"] = download_url.format(tools=self._container, **cfg)

        unpack_path = utils.get_item(cfg, "unpack_path") or ""
        if unpack_path is __missing__:
            unpack_path = ""
        assert isinstance(unpack_path, str), \
            f"Tool<{cfg['name']}>.unpack_path type error, " \
            f"str was expects, got {type(unpack_path)}"

        target_path = utils.get_item(cfg, "target_path") or ""
        if target_path is __missing__:
            target_path = ""
        assert isinstance(target_path, str), \
            f"Tool<{cfg['name']}>.target_path type error, " \
            f"str was expects, got {type(target_path)}"

        absolute_path = utils.get_item(cfg, "absolute_path") or ""
        if absolute_path is __missing__:
            absolute_path = ""
        assert isinstance(absolute_path, str), \
            f"Tool<{cfg['name']}>.absolute_path type error, " \
            f"str was expects, got {type(absolute_path)}"

        if download_url and not unpack_path and not target_path:
            target_path = utils.guess_file_name(download_url)

        # target path: {target_path}
        # unpack path: {unpack_path}
        # root path: {data_path}/tools/{unpack_path}/
        # absolute path: {data_path}/tools/{unpack_path}/{target_path}
        cfg["target_path"] = target_path.format(tools=self._container, **cfg)
        cfg["unpack_path"] = unpack_path.format(tools=self._container, **cfg)
        paths = ["tools"]
        if not utils.is_empty(cfg["unpack_path"]):
            paths.append(cfg["unpack_path"])
        cfg["root_path"] = self._container.environ.get_data_dir(*paths)

        if absolute_path:
            cfg["absolute_path"] = absolute_path.format(tools=self._container, **cfg)
        elif cfg["target_path"]:
            cfg["absolute_path"] = os.path.join(cfg["root_path"], cfg["target_path"])
        else:
            cfg["absolute_path"] = ""

        # set executable cmdline
        cmdline = utils.get_item(cfg, "cmdline") or ""
        if cmdline is __missing__:
            cmdline = cfg["name"]
        assert isinstance(cmdline, str), \
            f"Tool<{cfg['name']}>.cmdline type error, " \
            f"str was expects, got {type(absolute_path)}"
        cfg["cmdline"] = cmdline

        if not utils.is_empty(cmdline):
            cmdline = shutil.which(cmdline)
        if not utils.is_empty(cmdline):
            cfg["absolute_path"] = cmdline
            cfg["executable_cmdline"] = [cmdline]
        else:
            executable_cmdline = utils.get_item(cfg, "executable_cmdline")
            if executable_cmdline:
                assert isinstance(executable_cmdline, (str, Tuple, List)), \
                    f"Tool<{cfg['name']}>.executable_cmdline type error, " \
                    f"str/tuple/list was expects, got {type(executable_cmdline)}"
                # if executable_cmdline is not empty,
                # set the executable flag to false
                cfg["executable"] = False
            else:
                # if executable_cmdline is empty,
                # set absolute_path as executable_cmdline
                executable_cmdline = cfg["absolute_path"]
            if isinstance(executable_cmdline, str):
                executable_cmdline = [executable_cmdline]
            cfg["executable_cmdline"] = [str(i).format(tools=self._container, **cfg) \
                                         for i in executable_cmdline]

        return cfg

    def copy(self, **kwargs):
        return Tool(self._container, self._config, **kwargs)

    def prepare(self) -> None:
        for dependency in self.depends_on:
            tool = self._container[dependency]
            tool.prepare()

        # download and unzip file
        if self.exists:
            pass
        elif not self.download_url or not self.absolute_path:
            raise ToolError(
                f"{self} does not support on "
                f"{self._container.system} ({self._container.machine})")
        else:
            self._container.logger.info(f"Download {self}: {self.download_url}")
            url_file = self._container.environ.get_url_file(self.download_url)
            temp_dir = self._container.environ.get_temp_path("tools", "cache")
            temp_path = url_file.save(to_dir=temp_dir)
            if not utils.is_empty(self.unpack_path):
                self._container.logger.debug(f"Unpack {self} to {self.root_path}")
                shutil.unpack_archive(temp_path, self.root_path)
                os.remove(temp_path)
            else:
                self._container.logger.debug(f"Move {self} to {self.absolute_path}")
                shutil.move(temp_path, self.absolute_path)

        # change tool file mode
        if self.executable and not os.access(self.absolute_path, os.X_OK):
            self._container.logger.debug(f"Chmod 755 {self.absolute_path}")
            os.chmod(self.absolute_path, 0o0755)

    def clear(self) -> None:
        if not self.exists:
            self._container.logger.debug(f"{self} does not exist, skip")
            return
        if not utils.is_empty(self.unpack_path):
            self._container.logger.debug(f"Delete {self.root_path}")
            shutil.rmtree(self.root_path, ignore_errors=True)
        elif self.absolute_path.startswith(self.root_path):
            self._container.logger.debug(f"Delete {self.absolute_path}")
            os.remove(self.absolute_path)

    def popen(self, *args: [Any], **kwargs) -> utils.Popen:
        self.prepare()

        # java or other
        executable_cmdline = self.executable_cmdline
        if executable_cmdline[0] in self._container.items:
            args = [*executable_cmdline[1:], *args]
            tool = self._container.items[executable_cmdline[0]]
            return tool.popen(*args, **kwargs)

        return utils.Popen(*[*executable_cmdline, *args], **kwargs)

    @utils.timeoutable
    def exec(
            self,
            *args: [Any],
            timeout: utils.Timeout = None,
            ignore_errors: bool = False,
            log_output: bool = False,
            error_type: Type[Exception] = ToolExecError
    ) -> str:
        """
        执行命令
        :param args: 命令
        :param timeout: 超时时间
        :param ignore_errors: 忽略错误，报错不会抛异常
        :param log_output: 把输出打印到logger中
        :param error_type: 抛出异常类型
        :return: 返回stdout输出内容
        """
        process = self.popen(*args, capture_output=True)

        try:
            out, err = process.exec(
                timeout=timeout,
                on_stdout=self._container.logger.info if log_output else None,
                on_stderr=self._container.logger.error if log_output else None
            )
            if not ignore_errors and process.poll() not in (0, None):
                if isinstance(err, bytes):
                    err = err.decode(errors="ignore")
                    err = err.strip()
                elif isinstance(err, str):
                    err = err.strip()
                if err:
                    raise error_type(err)

            if isinstance(out, bytes):
                out = out.decode(errors="ignore")
                out = out.strip()
            elif isinstance(out, str):
                out = out.strip()

            return out or ""

        finally:
            process.kill()

    def __repr__(self):
        return f"Tool<{self.name}>"


class Tools(object):

    def __init__(self, env: "BaseEnviron", **kwargs):
        self.environ = env
        self.logger = env.get_logger("tools")

        self.config = kwargs
        self.config.setdefault("system", utils.get_system())
        self.config.setdefault("machine", utils.get_machine())
        self.config.setdefault("interpreter", sys.executable)

    @property
    def system(self) -> str:
        return self.config["system"]

    @property
    def machine(self) -> str:
        return self.config["machine"]

    @cached_property
    def items(self) -> Mapping[str, Tool]:
        items = {}
        for key in self.environ.config.keys():
            if not key.startswith("GENERAL_TOOL_"):
                continue
            value = self.environ.config.get(key)
            if not isinstance(value, dict):
                warnings.warn(f"dict was expected, got {type(value)}, ignored.")
                continue
            key = key[len("GENERAL_TOOL_"):]
            key = key.lower()
            name = value.setdefault("name", key)
            items[name] = Tool(self, value)
        return items

    def __iter__(self) -> Iterator[Tool]:
        return iter(self.items.values())

    def __getitem__(self, item) -> Tool:
        if item not in self.items:
            raise ToolNotFound(f"Not found tool {item}")
        return self.items[item]

    def __getattr__(self, item) -> Tool:
        if item not in self.items:
            raise ToolNotFound(f"Not found tool {item}")
        return self.items[item]
