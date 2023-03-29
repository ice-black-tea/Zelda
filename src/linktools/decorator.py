#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@author  : Hu Ji
@file    : decorator.py
@time    : 2019/01/15
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
import functools
import threading
import typing

_T = typing.TypeVar('_T')
_missing = object()


def singleton(cls: typing.Type[_T]) -> typing.Callable[..., _T]:
    instances = {}
    lock = threading.RLock()

    @functools.wraps(cls)
    def wrapper(*args, **kwargs):
        if cls not in instances:
            with lock:
                if cls not in instances:
                    instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return wrapper


def try_except(errors: typing.Tuple[typing.Type[BaseException]] = (Exception,), default: typing.Any = None):
    def decorator(fn: typing.Callable[..., _T]) -> typing.Callable[..., _T]:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs) -> _T:
            try:
                return fn(*args, **kwargs)
            except errors:
                return default

        return wrapper

    return decorator


def synchronized(lock=None):
    if lock is None:
        lock = threading.Lock()

    def decorator(fn: typing.Callable[..., _T]) -> typing.Callable[..., _T]:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs) -> _T:
            lock.acquire()
            try:
                return fn(*args, **kwargs)
            finally:
                lock.release()

        return wrapper

    return decorator


class cached_property:

    def __init__(self, func):
        self.func = func
        self.attrname = None
        self.__doc__ = func.__doc__
        self.lock = threading.RLock()

    def __set_name__(self, owner, name):
        if self.attrname is None:
            self.attrname = name
        elif name != self.attrname:
            raise TypeError(
                "Cannot assign the same cached_property to two different names "
                f"({self.attrname!r} and {name!r})."
            )

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        if self.attrname is None:
            raise TypeError(
                "Cannot use cached_property instance without calling __set_name__ on it.")
        try:
            cache = instance.__dict__
        except AttributeError:  # not all objects have __dict__ (e.g. class defines slots)
            msg = (
                f"No '__dict__' attribute on {type(instance).__name__!r} "
                f"instance to cache {self.attrname!r} property."
            )
            raise TypeError(msg) from None
        val = cache.get(self.attrname, _missing)
        if val is _missing:
            with self.lock:
                # check if another thread filled cache while we awaited lock
                val = cache.get(self.attrname, _missing)
                if val is _missing:
                    val = self.func(instance)
                    try:
                        cache[self.attrname] = val
                    except TypeError:
                        msg = (
                            f"The '__dict__' attribute on {type(instance).__name__!r} instance "
                            f"does not support item assignment for caching {self.attrname!r} property."
                        )
                        raise TypeError(msg) from None

        return val


class classproperty:
    """
    Decorator that converts a method with a single cls argument into a property
    that can be accessed directly from the class.
    """

    def __init__(self, func=None):
        self.func = func

    def __get__(self, instance, owner=None):
        return self.func(owner)


class cached_classproperty:

    def __init__(self, func):
        self.func = func
        self.__doc__ = func.__doc__
        self.lock = threading.RLock()
        self.val = _missing

    def __get__(self, instance, owner=None):
        if self.val is _missing:
            with self.lock:
                # check if another thread filled cache while we awaited lock
                if self.val is _missing:
                    self.val = self.func(owner)

        return self.val
