import os

from kubernetes import client, config


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
