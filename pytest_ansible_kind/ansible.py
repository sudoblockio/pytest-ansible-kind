import os
from typing import Any, Mapping

import yaml
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


def extract_play_hosts(playbook_path: str) -> list[str]:
    """
    Minimal parser to extract unique `hosts` patterns from a playbook.
    Returns an ordered list of unique host patterns (strings). Empty if none.
    """
    with open(playbook_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    plays: list[dict[str, Any]]
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
