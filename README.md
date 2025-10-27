# pytest-ansible-kind

<!---badges-start--->
[![Tests](https://github.com/sudoblockio-new/pytest-ansible-kind/actions/workflows/main.yaml/badge.svg?branch=main)](https://github.com/sudoblockio-new/pytest-ansible-kind/actions/workflows/main.yaml)
[![Copybara](https://github.com/sudoblockio-new/pytest-ansible-kind/actions/workflows/copy.yaml/badge.svg?branch=main)](https://github.com/sudoblockio-new/pytest-ansible-kind/actions/workflows/copy.yaml)
![GitHub Release Date](https://img.shields.io/github/release-date/sudoblockio-new/pytest-ansible-kind)
![GitHub tag (latest by date)](https://img.shields.io/github/v/tag/sudoblockio-new/pytest-ansible-kind)
![Copy job](https://img.shields.io/github/actions/workflow/status/sudoblockio-new/pytest-ansible-kind/copy.yaml?branch=main&job=copy)
<!---badges-end--->

Pytest plugins for running various ansible tests against kind k8s cluster managing setup and teardown and yielding a kubeconfig to build a client and make assertions with after the
playbook ran.

TODO: Document ini opts and behaviour

### `kind_run`

```python
def kind_run(
    *,
    playbook: str,  # path to playbook
    project_dir: str,  # path to the base of the collections directory
    inventory_file: str | None = None,  # Optionally supply inventory. Omit for local kind
) -> str:  # returns kubeconfig path
```

### Usage

```python
import pytest

import os
from kubernetes import client, config


@pytest.fixture(scope='function', autouse=True)
def collection_path(request):
    return os.path.dirname(os.path.dirname(__file__))


def test_k8s_run(collection_path, kind_run):
    kubeconfig = kind_run(
        # When not supplying inventory, assumes localhost for local kind
        playbook=os.path.join(collection_path, "playbooks", "playbook-k8s.yaml"),
        project_dir=collection_path,
    )

    assert isinstance(kubeconfig, str)
    assert os.path.isfile(kubeconfig)

    config.load_kube_config(config_file=kubeconfig)
    v1 = client.CoreV1Api()
    ns_names = {ns.metadata.name for ns in v1.list_namespace().items}
    assert "test-ns" in ns_names
```
