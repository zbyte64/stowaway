#misc for now
import random
import string
import os

from fabric.api import env, settings
from fabric.context_managers import remote_tunnel


boolean = lambda x: str(x).lower() in ['true', '1']


class patch_environ(object):
    def __init__(self, params=None, **kwargs):
        self.params = params or kwargs

    def __enter__(self):
        self.old_environ = os.environ.copy()
        os.environ.update(self.params)

    def __exit__(self, *args):
        os.environ = self.old_environ


class machine(object):
    def __init__(self, name):
        self.name = name

    def make_settings_patch(self):
        self.settings_patch = settings(
            host_string=env.VAGRANT.user_hostname_port(vm_name=self.name),
            key_filename=env.VAGRANT.keyfile(vm_name=self.name),
            disable_known_hosts=True)

    def make_environ_patch(self):
        self.environ_patch = patch_environ(VM_NAME=self.name)

    def __enter__(self):
        self.make_settings_patch()
        self.settings_patch.__enter__()
        self.make_environ_patch()
        self.environ_patch.__enter__()

    def __exit__(self, *args):
        self.settings_patch.__exit__(*args)
        self.environ_patch.__exit__(*args)


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
