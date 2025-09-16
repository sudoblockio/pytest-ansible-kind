# pytest-ansible-kind

Pytest plugins for running various ansible tests against kind k8s cluster managing setup and teardown and yielding a kubeconfig to build a client and make assertions with after the playbook ran.

## K8s / Kind

- `kind_run` params:
  - `playbook: str` - path to playbook
  - `project_dir: str` - path to the base of the collections directory
- Returns a `kubeconfig` string path which can be used for a client to make assertions

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
        playbook=os.path.join(collection_path, "tests", "playbook-k8s.yaml"),
        project_dir=collection_path,
    )

    assert isinstance(kubeconfig, str)
    assert os.path.isfile(kubeconfig)

    config.load_kube_config(config_file=kubeconfig)
    v1 = client.CoreV1Api()
    ns_names = {ns.metadata.name for ns in v1.list_namespace().items}
    assert "test-ns" in ns_names
```
