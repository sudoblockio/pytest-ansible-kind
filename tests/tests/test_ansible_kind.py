import os
from kubernetes import client, config

from pytest_ansible_kind import KindRunner


def test_ansible_kind_simple(kind_runner: KindRunner):
    kubeconfig = kind_runner("playbooks/playbook-override-hosts.yaml")

    assert isinstance(kubeconfig, str) and os.path.isfile(kubeconfig)
    config.load_kube_config(config_file=kubeconfig)
    v1 = client.CoreV1Api()
    ns_names = {ns.metadata.name for ns in v1.list_namespace().items}
    assert "foo-ns" in ns_names


def test_ansible_kind_with_inventory_and_config(kind_runner: KindRunner):
    kubeconfig = kind_runner(
        "tests/playbook-localhost.yaml",
        kind_config="tests/my-cluster.yaml",
        inventory_file="tests/inventory.ini",
        extravars={"my_var": "bar"},
    )

    assert isinstance(kubeconfig, str) and os.path.isfile(kubeconfig)
    config.load_kube_config(config_file=kubeconfig)
    v1 = client.CoreV1Api()
    ns_names = {ns.metadata.name for ns in v1.list_namespace().items}
    assert "bar-ns" in ns_names
