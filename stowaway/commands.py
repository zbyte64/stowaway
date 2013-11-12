# -*- coding: utf-8 -*
import os
import shutil
import json
import code
from pprint import pprint
from functools import wraps

from vagrant import Vagrant

from fabric.api import env, local, run, sudo, prompt, task


env.PROVISIONER = None
env.DOCKER_REGISTRY = None
env.TOOL_ROOT = os.path.split(os.path.abspath(__file__))[0]
env.ASSET_DIR = os.path.join(env.TOOL_ROOT, 'assets')
env.WORK_DIR = os.getcwd()
env.PROVISION_SETUPS = dict()
env.VAGRANT = None
env.SETTINGS_LOADED = False

#state sensitive
from .state import nodeCollection, instanceCollection, configCollection, \
    balancerCollection, appCollection, boxCollection
from .utils import machine, gencode, registry, patch_environ, boolean, MB


@task
def init_vagrant():
    if not os.path.exists(os.path.join(env.WORK_DIR, 'Vagrantfile')):
        shutil.copy(os.path.join(env.ASSET_DIR, 'Vagrantfile'),
                    env.WORK_DIR)
    if not os.path.exists(os.path.join(env.WORK_DIR, 'redis_cli.py')):
        shutil.copy(os.path.join(env.ASSET_DIR, 'redis_cli.py'),
                    env.WORK_DIR)
    env.VAGRANT = Vagrant(env.WORK_DIR)


@task
def embark():
    init_vagrant()
    options = env.PROVISION_SETUPS.keys()
    provisioner = prompt('What vessel shall to use? (%s)' % ', '.join(options),
        default='aws')
    provisioner = 'aws'
    return env.PROVISION_SETUPS[provisioner]()


def load_settings():
    environ = configCollection.get('environ') or dict()
    os.environ.update(environ)
    env.update(environ)
    if not env.VAGRANT:
        env.VAGRANT = Vagrant(env.WORK_DIR)
    env.SETTINGS_LOADED = True


def configuredtask(func):
    @wraps(func)
    def wrap(*args, **kwargs):
        if not env.SETTINGS_LOADED:
            load_settings()
        return func(*args, **kwargs)
    return task(wrap)


def _printobj(obj):
    if hasattr(obj, 'to_dict'):
        pprint(obj.to_dict(serial=True))
    else:
        pprint(obj)
    return obj


@configuredtask
def provision(name=None, boxname=None):
    if name is None:
        name = gencode(12)
    if boxname is None:
        box = boxCollection.first(default=True)
        if not box:
            assert False, 'Please set a default box configuration'
    else:
        box = boxCollection.find(label=boxname)

    with patch_environ(VM_NAME=name, **box.params):
        #TODO make this debug not break functionality
        #from vagrant import VAGRANT_EXE
        #import subprocess
        #def anon(*args):
            #command = [VAGRANT_EXE] + [arg for arg in args if arg is not None]
            #return subprocess.check_call(command, cwd=env.VAGRANT.root)
        #env.VAGRANT._run_vagrant_command = anon
        env.VAGRANT.up(vm_name=name, provider=env.PROVISIONER)

    cpu = env.get('CPU_CAPACITY', box.cpu)
    cpu = int(cpu) if cpu else None
    memory = env.get('MEMORY_CAPACITY', box.memory)
    memory = int(memory) if memory else None

    return _printobj(nodeCollection.create(
        name=name,
        hostname=env.VAGRANT.hostname(name),
        cpu_capacity=cpu,
        memory_capacity=memory,
    ))


@configuredtask
def remove_node(name):
    with patch_environ(VM_NAME=name):
        env.VAGRANT.destroy(vm_name=name)
    nodeCollection.get(name=name).remove()


@configuredtask
def set_registry(uri):
    env.DOCKER_REGISTRY = uri
    environ = configCollection.get('environ') or dict()
    environ['DOCKER_REGISTRY'] = uri
    configCollection['environ'] = environ


@configuredtask
def install_local_registry():
    print 'For better performance install the registry on the cluster (TODO)'
    path = prompt('Enter a directory path to store docker images', default='/tmp/docker-registry')
    if not os.path.exists(path):
        local('sudo mkdir %s' % path)
    local('sudo docker pull samalba/docker-registry')
    local('sudo docker run -d -p 5000:5000 -v {path}:/tmp/registry samalba/docker-registry'.format(path=path))
    set_registry('localhost:5000')


@configuredtask
def upload_image(imagename):
    if env.DOCKER_REGISTRY:
        info = {
            'imagename': imagename,
            'registry': env.DOCKER_REGISTRY,
        }
        local('sudo docker tag {imagename} {registry}/{imagename}'.format(**info))
        local('sudo docker push {registry}/{imagename}'.format(**info))
        return
    else:
        assert False, 'Please install a docker registry'
    return


@configuredtask
def run_image(imagename, name=None, ports='', memory=256, cpu=1,
        **envparams):
    ports = [port.strip() for port in ports.split('-') if port]
    memory = memory * MB  # convert MB to Bytes
    if not name:
        for node in nodeCollection.all():
            if node.can_fit(memory=memory, cpu=cpu):
                name = node.name
                break
    if not name:
        print 'Not enough space in the cluster, allocating a node'
        node = provision()
        name = node.name
    assert name, 'Please provision a new node to make room'

    e_args = ' '.join(['-e %s=%s' % (key, value)
        for key, value in envparams.items()])

    p_args = ' '.join(['-p %s' % port
        for port in ports])

    args = '%s %s -m=%s -c=%s' % (e_args, p_args, memory, cpu)
    args = args.strip()

    with machine(name):
        with registry():
            fullname = '%s/%s' % (env.TUNNELED_DOCKER_REGISTRY, imagename)
            sudo('docker pull %s' % fullname)
            result = sudo('docker run -d %s %s' % (args, fullname))

            container_id = result.strip().rsplit()[-1]

            paths = list()
            hostname = env.VAGRANT.hostname(name)

            if not ports:
                result = sudo('docker inspect %s' % container_id)
                response = json.loads(result.strip())
                mapping = response[0]['NetworkSettings']['PortMapping']['Tcp']
                ports = mapping.values()

            for port in ports:
                uri = '%s:%s' % (hostname, port.split(':')[0])
                paths.append(uri)

            return _printobj(instanceCollection.create(
                machine_name=name,
                image_name=imagename,
                memory=memory,
                cpu=cpu,
                container_id=container_id,
                paths=paths,
            ))


@configuredtask
def stop_instance(container_id):
    instance = instanceCollection.get(container_id=container_id)
    name = instance.machine_name
    with machine(name):
        sudo('docker stop %s' % container_id)
    instance.remove()


@configuredtask
def shut_it_down(*names):
    if not names:
        names = [node.name for node in nodeCollection.all()]
    for name in names:
        instances = instanceCollection.find(machine_name=name)
        for instance in instances:
            stop_instance(instance.container_id)
    balancerCollection.all().delete()


@configuredtask
def register_balancer(endpoint, redis, name=None, default=False):
    if name is None:
        name = gencode(12)
    return _printobj(balancerCollection.create(
        name=name,
        endpoint_uri=endpoint,
        redis_uri=redis,
        default=default,
    ))


@configuredtask
def add_app(name, imagename, balancername=None):
    if not balancername:
        balancername = balancerCollection.first(default=True).name
    return _printobj(appCollection.create(
        name=name,
        image_name=imagename,
        balancer_name=balancername
    ))


@configuredtask
def app_config(name, **environ):
    app = appCollection.get(name=name)
    app.environ.update(environ)
    return app.save()


@configuredtask
def app_remove_config(name, *keys):
    app = appCollection.get(name=name)
    for key in keys:
        app.environ.pop(key, None)
    return app.save()


@configuredtask
def app_scale(name, num=1, process=None):
    #num=-1 to descale
    num = int(num)
    app = appCollection.get(name=name)
    balancer = balancerCollection.get(name=app.balancer_name)
    if num > 0:
        for i in range(num):
            instance = run_image(app.image_name, **app.environ)
            redis_cli(balancer.redis_uri, 'rpush',
                      'frontend:%s' % name, instance.paths[0])
    elif num < 0:
        instances = iter(instanceCollection.find(image_name=app.image_name))
        for i in range(abs(num)):
            instance = instances.next()
            stop_instance(instance.container_id)


@configuredtask
def app_add_domain(name, domain):
    app = appCollection.get(name=name)
    balancer = balancerCollection.get(name=app.balancer_name)
    redis_cli(balancer.redis_uri, 'rpush', 'frontend:%s' % domain, name)


@configuredtask
def app_remove_domain(name, domain):
    app = appCollection.get(name=name)
    balancer = balancerCollection.get(name=app.balancer_name)
    #TODO lookup redis docs
    redis_cli(balancer.redis_uri, 'rpop', 'frontend:%s' % domain, name)


def redis_cli(uri, *args):
    #TODO
    return run('python redis_cli.py ' + uri + ' ' + ' '.join(["%s" % arg for arg in args]))


def list_collection(col):
    for obj in col.all():
        pprint(col.get_serializable(obj))


@configuredtask
def list_nodes():
    list_collection(nodeCollection)


@configuredtask
def list_instances():
    list_collection(instanceCollection)


@configuredtask
def list_config():
    list_collection(configCollection)


@configuredtask
def list_balancers():
    list_collection(balancerCollection)


@configuredtask
def list_apps():
    list_collection(appCollection)


@configuredtask
def vagrant(cmd='', name=None):
    if name:
        with patch_environ(VM_NAME=name):
            local('vagrant %s' % cmd)
    else:
        local('vagrant %s' % cmd)


@task
def build_base():
    base_path = os.path.join(env.TOOL_ROOT, 'dockerfiles')
    for name in os.listdir(base_path):
        full_path = os.path.join(base_path, name)
        if not name.startswith('.') and os.path.isdir(full_path):
            tag = 'system/%s' % name
            local('cd %s && sudo docker build -t="%s" .' % (full_path, tag))


@configuredtask
def install_app_mgmt(compile_base=True):
    compile_base = boolean(compile_base)
    if compile_base:
        build_base()
        upload_image('system/redis')
        upload_image('system/hipache')

    #TODO We don't need 2 whole cpu units, but at least one should be guaranteed
    redis_password = gencode(12)
    redis = run_image('system/redis', PASSWORD=redis_password)
    redis_uri = 'redis://:%s@%s/0' % (redis_password, redis.paths[0])

    hipache = run_image('system/hipache', ports='80:80', REDIS_URI=redis_uri)
    hipache_uri = 'http://' + hipache.paths[0]

    return register_balancer(hipache_uri, redis_uri, default=True)


@configuredtask
def dbshell():
    variables = {
        'nodes': nodeCollection,
        'instances': instanceCollection,
        'configs': configCollection,
        'balancers': balancerCollection,
        'apps': appCollection,
        'boxes': boxCollection,
        'env': env,
    }
    code.interact(local=variables)


#TODO cleanup import chain
from . import provisioners
