#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@author  : Hu Ji
@file    : repo.py 
@time    : 2024/3/22
@site    : https://github.com/ice-black-tea
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
import json
import os
import os.path
import shutil
from typing import TYPE_CHECKING, Dict, Any, List, Union, Callable, Tuple, Set

from filelock import FileLock

from .container import BaseContainer, SimpleContainer
from .repository import Repository
from .. import utils, Config
from .._environ import environ
from ..decorator import cached_property

if TYPE_CHECKING:
    from .._environ import BaseEnviron


class ContainerError(Exception):
    pass


class ContainerManager:

    def __init__(self, environ: "BaseEnviron", name: str = "aio"):  # all_in_one
        self.user = utils.get_user()
        self.uid = utils.get_uid()
        self.gid = utils.get_gid()

        self.environ = environ
        self.logger = environ.get_logger("container")

        self.config = self.environ.wrap_config()
        self.config.envvar_prefix = ""
        self.config.namespace = "CONTAINER"
        self.config.update_defaults(
            COMPOSE_PROJECT_NAME=name or self.environ.name,
            DOCKER_USER=Config.Prompt(default=os.environ.get("SUDO_USER", self.user), cached=True),
            DOCKER_PUID=Config.Lazy(lambda cfg: utils.get_uid(cfg.get("DOCKER_USER", type=str))),
            DOCKER_PGID=Config.Lazy(lambda cfg: utils.get_gid(cfg.get("DOCKER_USER", type=str))),
        )

        self.docker_container_name = "container.py"
        self.docker_compose_names = (
            "compose.yaml",
            "compose.yml",
            "docker-compose.yaml",
            "docker-compose.yml"
        )

    @property
    def debug(self):
        return os.environ.get("DEBUG", self.environ.debug)

    @property
    def system(self) -> str:
        return self.environ.system

    @property
    def machine(self) -> str:
        return self.environ.machine

    @cached_property
    def container_type(self):
        choices = ["docker", "docker-rootless", "podman"] \
            if self.system in ("darwin", "linux") and os.getuid() != 0 \
            else ["docker", "podman"]
        return self.config.get(
            "CONTAINER_TYPE",
            type=str,
            default=Config.Prompt(choices=choices, cached=True),
        )

    @cached_property
    def container_host(self):
        default = "/var/run/docker.sock"
        host = self.environ.get_config(
            "DOCKER_HOST",
            type=str,
            default=default
        )
        if host:
            left, sep, right = host.partition("://")
            return right or left
        return default

    @cached_property
    def host(self):
        return self.environ.get_config(
            "HOST",
            type=str,
            default=Config.Prompt(default=utils.get_lan_ip())
        )

    @cached_property
    def app_path(self):
        return self.config.get(
            "DOCKER_APP_PATH",
            type=str,
            default=Config.Prompt(
                default=Config.Lazy(
                    lambda cfg: self.environ.get_data_path("container", "app", create_parent=True)
                ),
                cached=True,
            )
        )

    @cached_property
    def app_data_path(self):
        return self.config.get(
            "DOCKER_APP_DATA_PATH",
            type=str,
            default=Config.Prompt(
                default=Config.Lazy(
                    lambda cfg: self.environ.get_data_path("container", "app_data", create_parent=True)
                ),
                cached=True,
            )
        )

    @cached_property
    def user_data_path(self):
        return self.config.get(
            "DOCKER_USER_DATA_PATH",
            type=str,
            default=Config.Prompt(
                default=Config.Lazy(
                    lambda cfg: self.environ.get_data_path("container", "user_data", create_parent=True)
                ),
                cached=True,
            )
        )

    @cached_property
    def download_path(self):
        return self.config.get(
            "DOCKER_DOWNLOAD_PATH",
            type=str,
            default=Config.Prompt(
                default=Config.Lazy(
                    lambda cfg: self.environ.get_data_path("container", "download", create_parent=True)
                ),
                cached=True,
            )
        )

    @cached_property
    def temp_path(self):
        return self.environ.get_temp_path("container", create_parent=True)

    @cached_property
    def containers(self) -> Dict[str, BaseContainer]:
        result = dict()
        for container in self._load_containers():
            if container.name in result:
                self.logger.debug(f"Container `{container.name}` already exists, overwrite.")
            result[container.name] = container
        with self._config_lock:
            for name in self._load_config(self._config_path):
                if name not in result:
                    self.logger.warning(f"Not found installed container `{name}`, skip.")
        return result

    def _load_containers(self) -> List[BaseContainer]:
        containers: List[BaseContainer] = []

        self.logger.debug(f"Load containers from assets")
        asset_path = environ.get_asset_path("containers")
        for container in self._walk_containers(asset_path, max_level=1):
            containers.append(container)

        for url, repo in self.get_all_repos().items():
            self.logger.debug(f"Load containers from repository `{url}`")
            repo_path = repo.get("repo_path")
            if not repo_path or not os.path.exists(repo_path) or not os.path.isdir(repo_path):
                self.logger.warning(f"Repository `{url}` not found, skip.")
                continue
            for container in self._walk_containers(repo_path, max_level=2):
                containers.append(container)

        return containers

    def _walk_containers(self, path: str, max_level: int):
        yield from self._load_container(path)
        if max_level <= 0:
            return
        for name in os.listdir(path):
            root_path = os.path.join(path, name)
            if os.path.isdir(root_path):
                yield from self._walk_containers(root_path, max_level - 1)

    def _load_container(self, path: str):
        if not os.path.isdir(path):
            return

        container_path = os.path.join(path, self.docker_container_name)
        if os.path.exists(container_path):
            try:
                name = path.replace(os.sep, ".")
                module = utils.lazy_import_file(name, container_path)
                for key, value in module.__dict__.items():
                    if isinstance(value, type) and issubclass(value, BaseContainer):
                        if not value.__abstract__:
                            container = value(self, path)
                            self.logger.debug(f"Load container {container.name} in {path}")
                            yield container
                            return
            except Exception as e:
                self.logger.warning(f"Failed to load container from `{path}`: {e}")

        for compose_name in self.docker_compose_names:
            compose_path = os.path.join(path, compose_name)
            if os.path.exists(compose_path):
                container = SimpleContainer(self, path)
                self.logger.debug(f"Load container {container.name} in {path}")
                yield container
                return

    def get_installed_containers(self) -> List[BaseContainer]:
        with self._config_lock:
            return self._load_installed_containers()

    def check_installed_containers(self):
        with self._config_lock:
            for name in self._load_config(self._config_path):
                if name not in self.containers:
                    self.logger.warning(f"Not found container {name}, skip.")

    def iter_installed_container_names(self):
        containers = self.get_installed_containers()
        containers = self.resolve_depend_containers(containers)
        for container in containers:
            yield container.name

    def resolve_depend_containers(self, containers: List[BaseContainer]) -> List[BaseContainer]:
        order = lambda o: o() if callable(o) else o
        result: Dict[BaseContainer, Union[int, Callable[[], int]]] = dict()
        container_queue: Set[BaseContainer] = set(containers)
        while container_queue:
            container = container_queue.pop()
            if not container.enable:
                self.logger.debug(f"Skip disabled container {container.name}")
                continue
            result.setdefault(container, container.order)
            for dependency in container.dependencies:
                if dependency not in self.containers:
                    raise ContainerError(f"Dependency container {dependency} not found")
                depend_container = self.containers[dependency]
                if not depend_container.enable:
                    continue
                if depend_container not in result:
                    result.setdefault(depend_container, depend_container.order)
                    container_queue.add(depend_container)
                if order(result[depend_container]) >= order(result[container]):
                    result[depend_container] = functools.partial(lambda o: order(result[o]) - 1, container)

        return sorted(result, key=lambda o: (order(result[o]), o.order, o.name))

    def prepare_installed_containers(self) -> List[BaseContainer]:
        self.logger.debug(f"Load container type: {self.container_type}")  # 加载容器类型
        containers = self.get_installed_containers()
        containers = self.resolve_depend_containers(containers)
        if not containers:
            raise ContainerError("No container installed")
        for container in reversed(containers):
            self.config.update_defaults(**container.configs)
        for container in containers:
            container.on_init()
        for container in containers:
            if container.docker_file and self.debug:  # 加载每个容器的dockerfile
                self.logger.debug(f"Generate Dockerfile for {container.name}")
            if container.docker_compose and self.debug:  # 加载每个容器的docker-compose.yml
                self.logger.debug(f"Generate docker-compose.yml for {container.name}")
        return containers

    def add_installed_containers(self, *names: str) -> List[BaseContainer]:
        with self._config_lock:
            result = set()
            for name in names:
                container = self.containers.get(name, None)
                if container:
                    result.add(container)
            installed_containers = self._load_installed_containers() + list(result)
            self._dump_installed_containers(installed_containers)
            return list(result)

    def remove_installed_containers(self, *names: str, force: bool = False) -> List[BaseContainer]:
        with self._config_lock:
            containers = self._load_installed_containers()

            result = set()
            remove_names = set(names)
            for name in set(names):
                if name not in self.containers:
                    continue
                for container in containers:
                    if not container.is_depend_on(name):
                        continue
                    if container.name in remove_names:
                        continue
                    if force:
                        remove_names.add(container.name)
                    elif container not in remove_names:
                        raise ContainerError(
                            f"{container} depends on {self.containers[name]}, "
                            f"cannot remove {self.containers[name]}"
                        )

            for name in remove_names:
                container = self.containers.get(name, None)
                if container and container in containers:
                    result.add(container)
                    containers.remove(container)

            self._dump_installed_containers(containers)

            return list(result)

    def _load_installed_containers(self) -> List[BaseContainer]:
        result = set()
        for name in self._load_config(self._config_path):
            if name in self.containers:
                result.add(self.containers[name])
        return list(result)

    def _dump_installed_containers(self, containers: List[BaseContainer]) -> None:
        self._dump_config(
            self._config_path,
            list(set([container.name for container in containers]))
        )

    def create_process(
            self,
            *args,
            privilege: bool = None,
            **kwargs
    ) -> utils.Popen:
        if "cwd" not in kwargs:
            kwargs["cwd"] = self.environ.get_data_path("container", create_parent=True)
        if privilege:
            if self.system in ("darwin", "linux") and self.uid != 0:
                args = ["sudo", *args]
        return utils.Popen(*args, **kwargs)

    def create_docker_process(
            self,
            *args,
            privilege: bool = None,
            **kwargs
    ) -> utils.Popen:
        commands = []
        if self.container_type in ("docker", "docker-rootless"):
            commands.extend(["docker"])
            if privilege is None:
                privilege = self.container_type == "docker"
        elif self.container_type == "podman":
            commands.extend(["podman"])
        else:
            raise ContainerError(f"Invalid container type: {self.container_type}")
        return self.create_process(*commands, *args, privilege=privilege, **kwargs)

    def create_docker_compose_process(
            self,
            containers: List[BaseContainer],
            *args: str,
            privilege: bool = None,
            **kwargs: Any
    ) -> utils.Popen:
        commands = []
        if self.container_type in ("docker", "docker-rootless"):
            commands.extend(["docker", "compose"])
            if privilege is None:
                privilege = self.container_type == "docker"
        elif self.container_type == "podman":
            commands.extend(["podman", "compose"])
        else:
            raise ContainerError(f"Invalid container type: {self.container_type}")

        options = []
        for container in containers:
            path = container.get_docker_compose_file()
            if path:
                options.extend(["-f", path])
        append_env = kwargs.get("append_env", dict())
        append_env.setdefault("COMPOSE_PROJECT_NAME", self.config.get("COMPOSE_PROJECT_NAME"))

        return self.create_process(*commands, *options, *args, append_env=append_env, privilege=privilege, **kwargs)

    def change_owner(self, path: str, user: str):
        if hasattr(os, "chown") and os.path.exists(path):
            info = os.stat(path)
            self.create_process(
                "chown", "-R", user, path,
                privilege=self.uid != info.st_uid or self.uid != utils.get_uid(user)
            ).check_call()

    def get_all_repos(self) -> Dict[str, Dict[str, str]]:
        with self._repo_lock:
            repos = self._load_config(self._repo_config_path)
        return repos

    def add_repo(self, url: str, branch: str = None, force: bool = False):

        with self._repo_lock:
            repos = self._load_config(self._repo_config_path)

            def ensure_repo_not_exist(key):
                if key not in repos:
                    return
                if not force:
                    raise ContainerError(f"Repository `{key}` already exists.")
                self._remove_repo_file(repos.pop(key))
                self._dump_config(self._repo_config_path, repos)

            if url.startswith("http://") or url.startswith("https://") or url.startswith("git@"):
                ensure_repo_not_exist(url)
                self.logger.info(f"Add git repository: {url}")
                repo_name = utils.guess_file_name(url)
                repo_path = self._choose_repo_path(repo_name)
                Repository.clone_with_progress(url, repo_path, branch)
                repos[url] = dict(type="git", repo_path=repo_path, repo_name=repo_name)

            else:
                path = os.path.abspath(os.path.expanduser(url))
                if not os.path.exists(path) or not os.path.isdir(path):
                    raise ContainerError(f"Invalid local path: {url}")

                ensure_repo_not_exist(path)
                self.logger.info(f"Add local repository: {path}")
                repo_name = utils.guess_file_name(path)
                repo_path = self._choose_repo_path(repo_name)
                os.symlink(path, repo_path, target_is_directory=True)
                repos[path] = dict(type="local", repo_path=repo_path, repo_name=repo_name)

            self._dump_config(self._repo_config_path, repos)

    def update_repos(self, force: bool = False):
        for url, meta in self.get_all_repos().items():
            repo_type = meta.get("type", None)
            repo_path = meta.get("repo_path", None)
            if repo_type == "git" and repo_path:
                self.logger.info(f"Update git repository: {url}")
                if not os.path.exists(repo_path):
                    Repository.clone_with_progress(url, repo_path)
                    continue
                repo = Repository(repo_path)
                if repo.is_dirty():
                    if not force:
                        raise ContainerError(f"Repository `{repo_path}` is dirty")
                    self.logger.warning(f"Repository `{repo_path}` is dirty, reset to HEAD")
                    repo.git.reset(hard=True)
                repo.update_with_progress()

    def remove_repo(self, url: str):
        with self._repo_lock:
            repos = self._load_config(self._repo_config_path)
            if url not in repos:
                raise ContainerError(f"Repository `{url}` not found.")
            self._remove_repo_file(repos.pop(url))
            self._dump_config(self._repo_config_path, repos)

    def _choose_repo_path(self, name: str):
        index = 0
        path = os.path.join(self._repo_path, name)
        while os.path.exists(path):
            path = os.path.join(self._repo_path, f"{name}_{index}")
            index += 1
        return path

    def _remove_repo_file(self, repo: Dict[str, str]):
        repo_path = repo.get("repo_path", None)
        if repo_path and os.path.exists(repo_path):
            if os.path.islink(repo_path):
                self.logger.info(f"Remove link {repo_path}")
                os.unlink(repo_path)
            elif os.path.isdir(repo_path):
                self.logger.info(f"Remove directory {repo_path}")
                shutil.rmtree(repo_path, ignore_errors=True)

    @cached_property
    def _config_lock(self):
        return FileLock(self.environ.get_data_path("container", "config", "container.lock", create_parent=True))

    @cached_property
    def _config_path(self):
        return self.environ.get_data_path("container", "config", "containers.yml", create_parent=True)

    @cached_property
    def _repo_lock(self):
        return FileLock(self.environ.get_data_path("container", "repo", "repo.lock", create_parent=True))

    @cached_property
    def _repo_path(self):
        return self.environ.get_data_path("container", "repo", create_parent=True)

    @cached_property
    def _repo_config_path(self):
        return self.environ.get_data_path("container", "repo", "repo.json", create_parent=True)

    def _load_config(self, path: str) -> Union[Dict, List, Tuple]:
        if os.path.exists(path):
            try:
                with open(path, "rt") as fd:
                    return json.load(fd)
            except Exception as e:
                self.logger.warning(f"Failed to load config file {path}: {e}")
        return {}

    def _dump_config(self, path: str, config: Union[Dict, List, Tuple]):
        try:
            with open(path, "wt") as fd:
                json.dump(config, fd, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.warning(f"Failed to dump config file {path}: {e}")
