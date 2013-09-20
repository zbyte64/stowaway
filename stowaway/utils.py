#misc for now
import random
import string

from fabric.api import env, settings


class machine(object):
    def __init__(self, name):
        self.name = name

    def make_settings_patch(self):
        self.settings_patch = settings(
            host_string=env.VAGRANT.user_hostname_port(vm_name=self.name),
            key_filename=env.VAGRANT.keyfile(vm_name=self.name),
            disable_known_hosts=True)

    def __enter__(self):
        self.make_settings_patch()
        self.settings_patch.__enter__()

    def __exit__(self):
        self.settings_patch.__exit__()


def gencode(size, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for x in range(size))
