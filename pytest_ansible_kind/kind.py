import pytest

import os
import subprocess
import tempfile
from contextlib import contextmanager
from typing import Any, Callable, Generator, Literal

from pytest_sb_ansible.ansible import run_playbook
from pytest_sb_ansible.util import require_bins

DEFAULT_KIND_NAME = "test-kind"


def pytest_addoption(parser):
    k = parser.getgroup("k8s")
    k.addoption("--k8s-name", action="store", default="kind")
    k.addoption("--k8s-wait", action="store", default="120s")
    k.addoption(
        "--k8s-shutdown", action="store", choices=("delete", "keep"), default="delete"
    )


def _kind_out(args: list[str]) -> str:
    return subprocess.check_output(["kind", *args], text=True)


def _ensure_kind(name: str, wait: str) -> None:
    require_bins("kind", "kubectl", "ansible-playbook")
    clusters = [ln.strip() for ln in _kind_out(["get", "clusters"]).splitlines()]
    if name not in clusters:
        subprocess.run(
            ["kind", "create", "cluster", f"--name={name}", f"--wait={wait}"],
            check=True,
        )


def _kubeconfig_path(name: str) -> str:
    p = os.path.join(tempfile.gettempdir(), f"{name}-kubeconfig")
    with open(p, "w") as fh:
        fh.write(_kind_out(["get", "kubeconfig", f"--name={name}"]))
    return p


@contextmanager
def kind_runner(
    *,
    name: str = DEFAULT_KIND_NAME,
    shutdown: Literal["delete", "keep"] = "delete",
    wait: str = "120s",
) -> Generator[Callable[[Any], str], None, None]:
    _ensure_kind(name=name, wait=wait)
    kubeconfig = _kubeconfig_path(name)

    def _runner(
        playbook: str,
        project_dir: str,
        extravars: dict[str, Any] | None = None,
    ) -> str:
        run_playbook(
            playbook=playbook,
            project_dir=project_dir,
            extravars=extravars or {},
            envvars={"KUBECONFIG": kubeconfig},
        )
        return kubeconfig

    try:
        yield _runner
    finally:
        if shutdown == "delete":
            subprocess.run(["kind", "delete", "cluster", f"--name={name}"], check=False)


@pytest.fixture(scope="module")
def kind_run(request):
    name = request.config.getoption("k8s_name")
    wait = request.config.getoption("k8s_wait")
    shutdown = request.config.getoption("k8s_shutdown")

    with kind_runner(name=name, wait=wait, shutdown=shutdown) as run:
        yield run
