from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from typing import Any, Generator

import yaml
import ansible_runner


def _require_bins(*bins: str) -> None:
    missing = [b for b in bins if shutil.which(b) is None]
    if missing:
        raise RuntimeError("Missing required binaries: " + ", ".join(missing))


def _run_kind_checked(cmd: list[str]) -> None:
    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        parts: list[str] = [
            f"KIND command failed (exit code {exc.returncode})",
            f"Command: {' '.join(exc.cmd) if isinstance(exc.cmd, (list, tuple)) else exc.cmd}",
        ]
        if exc.stdout:
            parts.append("--- stdout ---")
            parts.append(exc.stdout.rstrip())
        if exc.stderr:
            parts.append("--- stderr ---")
            parts.append(exc.stderr.rstrip())
        raise RuntimeError("\n".join(parts)) from exc


def _kind_out(args: list[str]) -> str:
    try:
        return subprocess.check_output(
            ["kind", *args],
            text=True,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as exc:
        msg = [
            "KIND command failed while capturing output",
            f"Command: {' '.join(exc.cmd) if isinstance(exc.cmd, (list, tuple)) else exc.cmd}",
            "--- output ---",
            (exc.output or "").rstrip(),
        ]
        raise RuntimeError("\n".join(msg)) from exc


def _cluster_exists(name: str) -> bool:
    clusters = [ln.strip() for ln in _kind_out(["get", "clusters"]).splitlines()]
    return name in clusters


def _kubeconfig_path(name: str) -> str:
    p = os.path.join(tempfile.gettempdir(), f"{name}-kubeconfig")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(_kind_out(["get", "kubeconfig", f"--name={name}"]))
    return p


def _derive_name_from_cfg(cfg_path: str | None) -> str:
    if cfg_path is None:
        return "kind"

    with open(cfg_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if isinstance(data, dict):
        name = data.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()

    return "kind"


def _ensure_kind(
    name: str, wait: str, cfg_path: str | None, use_name_arg: bool
) -> None:
    _require_bins("kind", "kubectl", "ansible-playbook")

    if _cluster_exists(name):
        return

    cmd: list[str] = ["kind", "create", "cluster", f"--wait={wait}"]
    if use_name_arg:
        cmd.append(f"--name={name}")
    if cfg_path is not None:
        cmd.extend(["--config", cfg_path])

    _run_kind_checked(cmd)


def _resolve_playbook_path(project_dir: str, playbook: str) -> str:
    if os.path.isabs(playbook):
        if os.path.exists(playbook):
            return playbook
        raise FileNotFoundError(f"playbook not found: {playbook!r}")
    candidate = os.path.join(project_dir, playbook)
    if os.path.exists(candidate):
        return candidate
    raise FileNotFoundError(
        "playbook not found relative to project_dir. "
        f"project_dir={project_dir!r}, playbook={playbook!r}, tried={candidate!r}",
    )


def _extract_play_hosts(playbook_path: str) -> list[str]:
    with open(playbook_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if isinstance(data, list):
        plays = [p for p in data if isinstance(p, dict)]
    elif isinstance(data, dict):
        plays = [data]
    else:
        return []

    seen: set[str] = set()
    out: list[str] = []
    for p in plays:
        h = p.get("hosts")
        if isinstance(h, str):
            hv = h.strip()
            if hv and hv not in seen:
                seen.add(hv)
                out.append(hv)
    return out


class KindRunner:
    def __init__(
        self,
        project_dir: str,
        *,
        name: str | None = None,
        wait: str = "120s",
        shutdown: bool = False,
        default_kind_cfg: str | None = None,
    ) -> None:
        self.project_dir = project_dir
        self.name = name
        self.wait = wait
        self.shutdown = shutdown
        self._default_kind_cfg = default_kind_cfg

    def __call__(
        self,
        playbook: str,
        project_dir: str | None = None,
        extravars: dict[str, Any] | None = None,
        inventory_file: str | None = None,
        kind_config: str | None = None,
    ) -> str:
        resolved_project_dir = project_dir or self.project_dir

        if kind_config is not None:
            cfg_path = kind_config
            if not os.path.isabs(cfg_path):
                cfg_path = os.path.join(resolved_project_dir, cfg_path)
        else:
            cfg_path = self._default_kind_cfg

        explicit_name = self.name is not None
        effective_name = self.name or _derive_name_from_cfg(cfg_path)

        _ensure_kind(
            name=effective_name,
            wait=self.wait,
            cfg_path=cfg_path,
            use_name_arg=explicit_name,
        )

        kubeconfig = _kubeconfig_path(effective_name)
        resolved_playbook = _resolve_playbook_path(resolved_project_dir, playbook)

        temp_inv_path: str | None = None
        artifact_dir: str | None = None

        try:
            if inventory_file:
                if os.path.isabs(inventory_file):
                    inventory_arg = inventory_file
                else:
                    inventory_arg = os.path.join(resolved_project_dir, inventory_file)
            else:
                patterns = _extract_play_hosts(resolved_playbook)
                host_aliases = patterns or ["localhost"]
                with tempfile.NamedTemporaryFile(
                    "w",
                    delete=False,
                    prefix="kind-inv-",
                    suffix=".ini",
                ) as tf:
                    for alias in host_aliases:
                        tf.write(f"{alias} ansible_connection=local\n")
                    temp_inv_path = tf.name
                inventory_arg = temp_inv_path

            artifact_dir = tempfile.mkdtemp(prefix="pytest-ansible-kind-artifacts-")
            roles_path = os.path.join(resolved_project_dir, "roles")

            def _event_handler(event: dict[str, Any]) -> None:
                stdout = event.get("stdout")
                if stdout:
                    print(stdout, flush=True)

            result = ansible_runner.run(
                private_data_dir=resolved_project_dir,
                project_dir=resolved_project_dir,
                playbook=resolved_playbook,
                inventory=inventory_arg,
                extravars=extravars or {},
                envvars={
                    "KUBECONFIG": kubeconfig,
                    "ANSIBLE_FORCE_COLOR": "1",
                },
                roles_path=roles_path,
                artifact_dir=artifact_dir,
                quiet=False,
                json_mode=False,
                event_handler=_event_handler,
                suppress_env_files=True,
            )

            status = result.status
            rc = result.rc
            if not (status == "successful" and rc == 0):
                raise RuntimeError(f"play failed: status={status}, rc={rc}")

            return kubeconfig
        finally:
            if temp_inv_path and os.path.exists(temp_inv_path):
                try:
                    os.unlink(temp_inv_path)
                except OSError:
                    pass
            if artifact_dir and os.path.isdir(artifact_dir):
                shutil.rmtree(artifact_dir, ignore_errors=True)
            if self.shutdown:
                subprocess.run(
                    ["kind", "delete", "cluster", f"--name={effective_name}"],
                    check=False,
                )


@contextmanager
def kind_session(
    project_dir: str,
    *,
    name: str | None = None,
    wait: str = "120s",
    shutdown: bool = False,
    kind_cfg: str | None = None,
) -> Generator[KindRunner, None, None]:
    runner = KindRunner(
        project_dir=project_dir,
        name=name,
        wait=wait,
        shutdown=shutdown,
        default_kind_cfg=kind_cfg,
    )
    yield runner
