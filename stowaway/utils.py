#misc for now
import random
import string
import os
import socket

from fabric.thread_handling import ThreadHandler
from fabric.api import env, settings
from fabric.state import connections
from fabric.context_managers import _forwarder, documented_contextmanager #remote_tunnel


GB = 1024 ** 3
MB = 1024 ** 2

boolean = lambda x: str(x).lower() in ['true', '1']


class patch_environ(object):
    def __init__(self, params=None, **kwargs):
        self.params = params or kwargs

    def __enter__(self):
        self.old_environ = os.environ.copy()
        os.environ.update(self.params)

    def __exit__(self, *args):
        os.environ.clear()
        os.environ.update(self.old_environ)


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
        self.make_environ_patch()
        self.environ_patch.__enter__()
        self.make_settings_patch()
        self.settings_patch.__enter__()

    def __exit__(self, *args):
        self.settings_patch.__exit__(*args)
        self.environ_patch.__exit__(*args)


@documented_contextmanager
def remote_tunnel(remote_port, local_port=None, local_host="localhost",
    remote_bind_address="127.0.0.1"):
    """
    Create a tunnel forwarding a locally-visible port to the remote target.

    For example, you can let the remote host access a database that is
    installed on the client host::

        # Map localhost:6379 on the server to localhost:6379 on the client,
        # so that the remote 'redis-cli' program ends up speaking to the local
        # redis-server.
        with remote_tunnel(6379):
            run("redis-cli -i")

    The database might be installed on a client only reachable from the client
    host (as opposed to *on* the client itself)::

        # Map localhost:6379 on the server to redis.internal:6379 on the client
        with remote_tunnel(6379, local_host="redis.internal")
            run("redis-cli -i")

    ``remote_tunnel`` accepts up to four arguments:

    * ``remote_port`` (mandatory) is the remote port to listen to.
    * ``local_port`` (optional) is the local port to connect to; the default is
      the same port as the remote one.
    * ``local_host`` (optional) is the locally-reachable computer (DNS name or
      IP address) to connect to; the default is ``localhost`` (that is, the
      same computer Fabric is running on).
    * ``remote_bind_address`` (optional) is the remote IP address to bind to
      for listening, on the current target. It should be an IP address assigned
      to an interface on the target (or a DNS name that resolves to such IP).
      You can use "0.0.0.0" to bind to all interfaces.

    .. note::
        By default, most SSH servers only allow remote tunnels to listen to the
        localhost interface (127.0.0.1). In these cases, `remote_bind_address`
        is ignored by the server, and the tunnel will listen only to 127.0.0.1.

    .. versionadded: 1.6
    """
    if local_port is None:
        local_port = remote_port

    sockets = []
    channels = []
    threads = []

    def accept(channel, (src_addr, src_port), (dest_addr, dest_port)):
        channels.append(channel)
        sock = socket.socket()
        sockets.append(sock)

        try:
            sock.connect((local_host, local_port))
        except Exception, e:
            print "[%s] rtunnel: cannot connect to %s:%d (from local)" % (env.host_string, local_host, local_port)
            chan.close()
            return

        #print "[%s] rtunnel: opened reverse tunnel: %r -> %r -> %r"\
        #      % (env.host_string, channel.origin_addr,
        #         channel.getpeername(), (local_host, local_port))

        th = ThreadHandler('fwd', _forwarder, channel, sock)
        threads.append(th)

    transport = connections[env.host_string].get_transport()
    transport.request_port_forward(remote_bind_address, remote_port, handler=accept)

    try:
        yield
    finally:
        for sock, chan, th in zip(sockets, channels, threads):
            sock.close()
            chan.close()
            th.thread.join(timeout=1)
            th.raise_if_needed()
        transport.cancel_port_forward(remote_bind_address, remote_port)


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
        transport = connections[env.host_string].get_transport()
        transport.cancel_port_forward('127.0.0.1', 5000)
        self.tunnel_patch.__exit__(*args)
        env.TUNNELED_DOCKER_REGISTRY = None


def gencode(size, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for x in range(size))
