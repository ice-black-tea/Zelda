#!/usr/bin/env python3
# -*- coding:utf-8 -*-

"""
@author  : Hu Ji
@file    : _config.py
@time    : 2023/05/20
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
import configparser
import errno
import json
import os
import pickle
import threading
from types import ModuleType
from typing import \
    TYPE_CHECKING, TypeVar, Type, Optional, Generator, \
    Any, Tuple, IO, Mapping, Union, List, Dict, Callable

from .decorator import cached_property
from .metadata import __missing__
from .rich import prompt, confirm, choose

if TYPE_CHECKING:
    from ._environ import BaseEnviron

    T = TypeVar("T")
    EnvironType = TypeVar("EnvironType", bound=BaseEnviron)


def _cast_bool(obj: Any) -> bool:
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, str):
        data = obj.lower()
        if data in ("true", "yes", "y", "on", "1"):
            return True
        elif data in ("false", "no", "n", "off", "0"):
            return False
        raise TypeError(f"str '{obj}' cannot be converted to type bool")
    return bool(obj)


def _cast_str(obj: Any) -> str:
    if isinstance(obj, str):
        return obj
    if obj is None:
        return ""
    return str(obj)


_CONFIG_ENV = "ENV"

_CONFIG_TYPES: "Dict[Type[T], Callable[[Any], T]]" = {
    bool: _cast_bool,
    str: _cast_str,
}


class ConfigError(Exception):
    pass


class ConfigParser(configparser.ConfigParser):

    def optionxform(self, optionstr):
        return optionstr


class ConfigProperty(abc.ABC):
    __lock__ = threading.RLock()

    def __init__(self, type: Type = None, cached: Union[bool, str] = False):
        self._data: Union[str, object] = __missing__
        self._type = type
        self._cached = cached

    def load(self, config: "Config", key: str, type: Type = None) -> Any:
        if self._data is not __missing__:
            return self._data
        with self.__lock__:
            if self._data is not __missing__:
                return self._data
            type = type or self._type
            if self._cached:
                # load cache from config file
                config_parser = ConfigParser()
                if os.path.exists(config.path):
                    config_parser.read(config.path)
                config_section = f"{config.namespace}.CACHE".upper()
                if isinstance(self._cached, str):
                    config_section = self._cached
                config_cache = __missing__
                if config_parser.has_option(config_section, key):
                    config_cache = config_parser.get(config_section, key)

                # load config value
                result = self._load(config, key, config_cache)
                if isinstance(result, ConfigProperty):
                    result = result.load(config, key, type=type)
                elif type and not isinstance(result, type):
                    result = config.cast(result, type)

                # update cache to config file
                if config_section == config_parser.default_section:
                    pass
                elif not config_parser.has_section(config_section):
                    config_parser.add_section(config_section)
                config_parser.set(config_section, key, str(result))
                with open(config.path, "wt") as fd:
                    config_parser.write(fd)

                self._data = result
            else:
                result = self._load(config, key, __missing__)
                if isinstance(result, ConfigProperty):
                    result = result.load(config, key, type=type)
                elif type and not isinstance(result, type):
                    result = config.cast(result, type)
                self._data = result
            return self._data

    @abc.abstractmethod
    def _load(self, config: "Config", key: str, cache: Any):
        pass


class ConfigDict(dict):

    def update_from_pyfile(self, filename: str, silent: bool = False) -> bool:
        d = ModuleType("config")
        d.__file__ = filename
        d.prompt = Config.Prompt
        d.lazy = Config.Lazy
        d.alias = Config.Alias
        d.sample = Config.Sample
        d.confirm = Config.Confirm
        try:
            with open(filename, "rb") as config_file:
                exec(compile(config_file.read(), filename, "exec"), d.__dict__)
        except OSError as e:
            if silent and e.errno in (errno.ENOENT, errno.EISDIR, errno.ENOTDIR):
                return False
            e.strerror = f"Unable to load configuration file ({e.strerror})"
            raise
        self.update_from_object(d)
        return True

    def update_from_file(self, filename: str, load: Callable[[IO[Any]], Mapping], silent: bool = False) -> bool:
        try:
            with open(filename, "rb") as f:
                obj = load(f)
        except OSError as e:
            if silent and e.errno in (errno.ENOENT, errno.EISDIR):
                return False

            e.strerror = f"Unable to load configuration file ({e.strerror})"
            raise

        return self.update_from_mapping(obj)

    def update_from_object(self, obj: Union[object, str]) -> None:
        for key in dir(obj):
            if key[0].isupper():
                self[key] = getattr(obj, key)

    def update_from_mapping(self, mapping: Optional[Mapping[str, Any]] = None, **kwargs: Any) -> bool:
        mappings: Dict[str, Any] = {}
        if mapping is not None:
            mappings.update(mapping)
        mappings.update(kwargs)
        for key, value in mappings.items():
            if key[0].isupper():
                self[key] = value
        return True


class Config:

    def __init__(self, environ: "BaseEnviron", default: ConfigDict, share: bool = False):
        self._environ = environ
        self._config = default if share else pickle.loads(pickle.dumps(default))
        self._envvar_prefix = f"{self._environ.name.upper()}_"
        self._namespace = configparser.DEFAULTSECT

    @property
    def envvar_prefix(self) -> str:
        """
        环境变量前缀
        """
        return self._envvar_prefix

    @envvar_prefix.setter
    def envvar_prefix(self, value: str):
        """
        环境变量前缀
        """
        self._envvar_prefix = value

    @property
    def namespace(self) -> str:
        """
        配置文件的对应的节
        """
        return self._namespace

    @namespace.setter
    def namespace(self, value: str):
        """
        配置文件的节
        """
        self._namespace = value

    @cached_property
    def path(self) -> str:
        """
        存放配置的目录
        """
        return self._environ.get_data_path(f"{self._environ.name}.cfg", create_parent=True)

    def load_from_env(self):
        """
        从缓存中加载配置
        """
        if os.path.exists(self.path):
            try:
                config_parser = ConfigParser()
                config_parser.read(self.path)
                if not config_parser.has_section(_CONFIG_ENV):
                    config_parser.add_section(_CONFIG_ENV)
                    with open(self.path, "wt") as fd:
                        config_parser.write(fd)
                for key, value in config_parser.items(_CONFIG_ENV):
                    self.set(key, value)
            except Exception as e:
                self._environ.logger.warning(f"Load config from {self.path} failed: {e}")

    def cast(self, obj: Optional[str], type: "Type[T]", default: Any = __missing__) -> "T":
        """
        类型转换
        """
        if type is not None and type is not __missing__:
            cast = _CONFIG_TYPES.get(type, type)
            try:
                return cast(obj)
            except Exception as e:
                if default is not __missing__:
                    return default
                raise e
        return obj

    def get(self, key: str, type: "Type[T]" = None, default: Any = __missing__) -> "T":
        """
        获取指定配置，优先会从环境变量中获取
        """
        last_error = __missing__
        try:
            env_key = f"{self.envvar_prefix}{key}"
            if env_key in os.environ:
                value = os.environ.get(env_key)
                return self.cast(value, type=type)

            if key in self._config:
                value = self._config.get(key)
                if isinstance(value, ConfigProperty):
                    return value.load(self, key, type=type)
                return self.cast(value, type=type)

        except Exception as e:
            last_error = e

        if default is __missing__:
            if last_error is not __missing__:
                raise last_error
            raise ConfigError(f"Not found environment variable \"{self.envvar_prefix}{key}\" or config \"{key}\"")

        if isinstance(default, ConfigProperty):
            return default.load(self, key, type=type)

        return default

    def keys(self) -> Generator[str, None, None]:
        """
        遍历配置名，默认不遍历内置配置
        """
        keys = set(self._config.keys())
        for key in os.environ.keys():
            if key.startswith(self._envvar_prefix):
                keys.add(key[len(self._envvar_prefix):])
        for key in sorted(keys):
            yield key

    def items(self) -> Generator[Tuple[str, Any], None, None]:
        """
        遍历配置项，默认不遍历内置配置
        """
        for key in self.keys():
            yield key, self.get(key)

    def set(self, key: str, value: Any) -> None:
        """
        更新配置
        """
        self._config[key] = value

    def set_default(self, key: str, value: Any) -> Any:
        """
        设置默认配置
        """
        return self._config.setdefault(key, value)

    def update(self, **kwargs) -> None:
        """
        更新配置
        """
        self._config.update(**kwargs)

    def update_defaults(self, **kwargs) -> None:
        """
        更新默认配置
        """
        for key, value in kwargs.items():
            self._config.setdefault(key, value)

    def update_from_file(self, path: str, load: Callable[[IO[Any]], Mapping] = None) -> bool:
        """
        加载配置文件，按照扩展名来匹配相应的加载规则
        """
        if load is not None:
            return self._config.update_from_file(path, load=load)
        if path.endswith(".py"):
            return self._config.update_from_pyfile(path)
        elif path.endswith(".json"):
            return self._config.update_from_file(path, load=json.load)
        self._environ.logger.debug(f"Unsupported config file: {path}")
        return False

    def update_from_dir(self, path: str, recursion: bool = False) -> bool:
        """
        加载配置文件目录，按照扩展名来匹配相应的加载规则
        """
        # 路径不存在
        if not os.path.exists(path):
            return False
        # 如果不是目录
        if not os.path.isdir(path):
            return self.update_from_file(path)
        # 如果不需要递归，那只要取一级目录就好了
        if not recursion:
            for name in os.listdir(path):
                config_path = os.path.join(path, name)
                if not os.path.isdir(config_path):
                    self.update_from_file(config_path)
            return True
        # 剩下的就是需要递归读取所有文件的情况了
        for root, dirs, files in os.walk(path, topdown=False):
            for name in files:
                self.update_from_file(os.path.join(root, name))
        return True

    def __getitem__(self, key: str) -> Any:
        return self.get(key)

    def __setitem__(self, key: str, value: Any):
        self.set(key, value)

    class Prompt(ConfigProperty):

        def __init__(
                self,
                prompt: str = None,
                password: bool = False,
                choices: Optional[List[str]] = None,
                type: Type[Union[str, int, float]] = str,
                default: Any = __missing__,
                cached: Union[bool, str] = False,
                always_ask: bool = False,
                allow_empty: bool = False,
        ):
            super().__init__(type=type, cached=cached)

            self.type = type
            self.prompt = prompt
            self.password = password
            self.choices = choices
            self.default = default
            self.always_ask = always_ask
            self.allow_empty = allow_empty

        def _load(self, config: "Config", key: str, cache: Any):

            default = cache
            if default is not __missing__ and not self.always_ask:
                if not config.get("RELOAD_CONFIG", type=bool, default=False):
                    return default

            if default is __missing__:
                default = self.default
                if isinstance(default, ConfigProperty):
                    default = default.load(config, key)

            if default is not __missing__:
                default = config.cast(default, self.type)

            if self.choices:
                index = choose(
                    self.prompt or f"Please choose {key}",
                    choices=self.choices,
                    default=default,
                    show_default=True,
                    show_choices=True
                )
                return self.choices[index]

            return prompt(
                self.prompt or f"Please input {key}",
                type=self.type,
                password=self.password,
                choices=self.choices,
                default=default,
                allow_empty=self.allow_empty,
                show_default=True,
                show_choices=True
            )

    class Confirm(ConfigProperty):

        def __init__(
                self,
                prompt: str = None,
                default: Any = __missing__,
                cached: Union[bool, str] = False,
                always_ask: bool = False,
        ):
            super().__init__(type=bool, cached=cached)

            self.prompt = prompt
            self.default = default
            self.always_ask = always_ask

        def _load(self, config: "Config", key: str, cache: Any):

            default = cache
            if default is not __missing__ and not self.always_ask:
                if not config.get("RELOAD_CONFIG", type=bool, default=False):
                    return default

            if default is __missing__:
                default = self.default
                if isinstance(default, ConfigProperty):
                    default = default.load(config, key)

            if default is not __missing__:
                default = config.cast(default, bool)

            return confirm(
                self.prompt or f"Please confirm {key}",
                default=default,
                show_default=True,
            )

    class Alias(ConfigProperty):

        DEFAULT = object()

        def __init__(
                self,
                *keys: str,
                type: Type = str,
                default: Any = __missing__,
                cached: Union[bool, str] = False
        ):
            super().__init__(type=type, cached=cached)
            self.keys = keys
            self.default = default

        def _load(self, config: "Config", key: str, cache: Any):
            if cache is not __missing__:
                return cache

            if self.default is __missing__:
                last_error = None
                for key in self.keys:
                    try:
                        return config.get(key)
                    except Exception as e:
                        last_error = e
                if last_error is not None:
                    raise last_error

            else:
                for key in self.keys:
                    result = config.get(key, default=self.DEFAULT)
                    if result is not self.DEFAULT:
                        return result

                return self.default

    class Lazy(ConfigProperty):

        def __init__(self, func: "Callable[[Config], T]"):
            super().__init__()
            self.func = func

        def _load(self, config: "Config", key: str, cache: Any):
            return self.func(config)

    class Sample(ConfigProperty):

        def __init__(self, data: Union[str, Dict[str, str]] = None):
            super().__init__()
            self.data = data

        def _load(self, config: "Config", key: str, cache: Any):
            message = \
                f"Cannot find config \"{key}\". {os.linesep}" \
                f"You can use any of the following methods to fix it: {os.linesep}" \
                f"1. set \"{config.envvar_prefix}{key}\" as an environment variable,{os.linesep}" \
                f"2. set \"{key}\" in [{_CONFIG_ENV}] section of {config.path}, such as: {os.linesep}" \
                f"   [{_CONFIG_ENV}] {os.linesep}" \
                f"   KEY1 = value1 {os.linesep}" \
                f"   KEY2 = value2 {os.linesep}"
            if self.data:
                if isinstance(self.data, Dict):
                    for key, value in self.data.items():
                        message += f"=> {key} = {value} {os.linesep}"
                else:
                    message += f"=> {self.data} {os.linesep}"
            else:
                message += f"=> {key} = <value> <= add this line {os.linesep}"

            raise ConfigError(message.rstrip())


class ConfigWrapper(Config):

    def __init__(self, config: "Config"):
        super().__init__(
            config._environ,
            config._config,
            share=True
        )
