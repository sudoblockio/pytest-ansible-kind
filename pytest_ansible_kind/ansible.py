import os
from typing import Any, Mapping

from ansible_runner import Runner, RunnerConfig


def run_playbook(
    playbook: str,
    *,
    project_dir: str,
    roles_path: str | None = None,
    inventory: str = "localhost,",
    extravars: Mapping[str, Any] | None = None,
    envvars: Mapping[str, str] | None = None,
    artifact_subdir: str = ".artifacts",
) -> None:
    rcfg = RunnerConfig(
        project_dir=project_dir,
        private_data_dir=project_dir,
        roles_path=roles_path or os.path.join(project_dir, "roles"),
        playbook=playbook,
        inventory=inventory,
        artifact_dir=os.path.join(project_dir, artifact_subdir),
        extravars=dict(extravars or {}),
        envvars=dict(envvars or {}),
    )
    rcfg.prepare()
    status, rc = Runner(config=rcfg).run()

    if not (status == "successful" and rc == 0):
        raise RuntimeError(f"play failed: status={status}, rc={rc}")
