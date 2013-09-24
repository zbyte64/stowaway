#misc for now
import random
import string
import os

from fabric.api import env, settings
from fabric.context_managers import remote_tunnel


class machine(object):
    def __init__(self, name):
        self.name = name

    def make_settings_patch(self):
        self.settings_patch = settings(
            host_string=env.VAGRANT.user_hostname_port(vm_name=self.name),
            key_filename=env.VAGRANT.keyfile(vm_name=self.name),
            disable_known_hosts=True)

    def __enter__(self):
        self.old_vm_name = os.environ.get('VM_NAME', '')
        os.environ['VM_NAME'] = self.name
        self.make_settings_patch()
        self.settings_patch.__enter__()

    def __exit__(self, *args):
        self.settings_patch.__exit__(*args)
        os.environ['VM_NAME'] = self.old_vm_name


class registry(object):
    '''
    Tunnels the local docker registry to the host machine
    '''
    def __enter__(self):
        local_host, local_port = env.DOCKER_REGISTRY.split(':', 1)
        self.tunnel_patch = remote_tunnel(5000, int(local_port), local_host)
        env.TUNNELED_DOCKER_REGISTRY = 'localhost:5000'
        self.tunnel_patch.__enter__()

    def __exit__(self, *args):
        self.tunnel_patch.__exit__(*args)
        env.TUNNELED_DOCKER_REGISTRY = None


def gencode(size, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for x in range(size))
