import os
from kubernetes import client, config


def test_override_hosts_inventory_default(kind_run):
    kubeconfig = kind_run("playbooks/playbook-override-hosts.yaml")

    assert isinstance(kubeconfig, str) and os.path.isfile(kubeconfig)
    config.load_kube_config(config_file=kubeconfig)
    v1 = client.CoreV1Api()
    ns_names = {ns.metadata.name for ns in v1.list_namespace().items}
    assert "foo-ns" in ns_names


def test_with_inventory(collection_path, kind_run):
    kubeconfig = kind_run(
        "tests/playbook-localhost.yaml",
        inventory_file="tests/inventory.ini",
        extravars={"my_var": "bar"},
    )

    assert isinstance(kubeconfig, str) and os.path.isfile(kubeconfig)
    config.load_kube_config(config_file=kubeconfig)
    v1 = client.CoreV1Api()
    ns_names = {ns.metadata.name for ns in v1.list_namespace().items}
    assert "bar-ns" in ns_names
