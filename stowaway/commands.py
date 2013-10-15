# -*- coding: utf-8 -*
import os
import shutil
import json
from pprint import pprint
from functools import wraps

from vagrant import Vagrant

from fabric.api import env, local, run, sudo, prompt, task


env.AWS_BOX = 'https://github.com/mitchellh/vagrant-aws/raw/master/dummy.box'
env.PROVISIONER = None
env.DOCKER_REGISTRY = None
env.TOOL_ROOT = os.path.split(os.path.split(os.path.abspath(__file__))[0])[0]
env.WORK_DIR = os.getcwd()
env.PROVISION_SETUPS = dict()
env.VAGRANT = None
env.SETTINGS_LOADED = False

#state sensitive
from .state import nodeCollection, instanceCollection, configCollection, \
    balancerCollection, appCollection
from .utils import machine, gencode, registry


@task
def embark(workingdir=None):
    if not os.path.exists(os.path.join(env.WORK_DIR, 'Vagrantfile')):
        shutil.copy(os.path.join(env.TOOL_ROOT, 'Vagrantfile'),
                    env.WORK_DIR)
    env.VAGRANT = Vagrant(env.WORK_DIR)
    provisioner = prompt('What vessel shall to use? (aws|[todo])')
    provisioner = 'aws'
    return env.PROVISION_SETUPS[provisioner]()


def setupaws():
    environ = dict()
    environ['PROVISIONER'] = 'aws'
    environ['BOX_NAME'] = 'awsbox'

    #ports 23 and 80 are required
    environ['AWS_SECURITY_GROUPS'] = prompt('Enter AWS security group', default='dockcluster')
    environ['AWS_AMI'] = prompt('Enter AWS AMI', default='ami-e1357b88')
    environ['AWS_MACHINE'] = prompt('Enter AWS Machine Size', default='m1.small')
    environ['AWS_ACCESS_KEY_ID'] = prompt('Enter your AWS Access Key ID')
    environ['AWS_SECRET_ACCESS_KEY'] = prompt('Enter your AWS Secret Access Key')
    environ['AWS_KEYPAIR_NAME'] = prompt('Enter your AWS Key pair name')
    default_pem_path = os.path.join(os.path.expanduser('~/.ssh'), environ['AWS_KEYPAIR_NAME'] + '.pem')
    environ['AWS_SSH_PRIVKEY'] = prompt('Enter your AWS SSH private key path', default=default_pem_path)
    configCollection['environ'] = environ

    load_settings()

    env.VAGRANT.box_add('awsbox', env.AWS_BOX, provider='aws', force=True)

env.PROVISION_SETUPS['aws'] = setupaws


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
def provision(name=None):
    if name is None:
        name = gencode(12)
    os.environ['VM_NAME'] = name  # normally handled by machine
    env.VAGRANT.up(vm_name=name, provider=env.PROVISIONER)

    #TODO support box settings, ie box1 = m1.medium, us-east1
    cpu = env.get('CPU_CAPACITY')
    cpu = int(cpu) if cpu else None
    memory = env.get('MEMORY_CAPACITY')
    memory = int(memory) if memory else None

    return _printobj(nodeCollection.create(
        name=name,
        hostname=env.VAGRANT.hostname(name),
        cpu_capacity=cpu,
        memory_capacity=memory,
    ))


@configuredtask
def remove_node(name):
    os.environ['VM_NAME'] = name  # normally handled by machine:
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
    local('sudo docker pull samalba/docker-registry')
    #TODO mount tmp directory for persistance
    #-volumes-from=""
    #-v /mnt/data_on_host:/var/lib/couchdb
    local('sudo docker run -d -p 5000:5000 samalba/docker-registry')
    set_registry('localhost:5000')


@configuredtask
def export_image(imagename):
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
def run_image(imagename, name=None, ports='', memory=256, cpu=1, **envparams):
    ports = [port.strip() for port in ports.split('-') if port]
    memory = memory * (1024 ** 3)  # convert MB to Bytes
    if not name:
        for node in nodeCollection.all():
            if node.can_fit(memory=memory, cpu=cpu):
                name = node.name
                break
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
def register_balancer(endpoint, redis, name=None):
    if name is None:
        name = gencode(12)
    return _printobj(balancerCollection.create(
        name=name,
        endpoint_uri=endpoint,
        redis_uri=redis
    ))


@configuredtask
def add_app(name, imagename, balancername):
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
        os.environ['VM_NAME'] = name
        local('vagrant %s' % cmd)
    else:
        local('vagrant %s' % cmd)


@task
def build_base():
    base_path = os.path.join(env.TOOL_ROOT, 'stowaway', 'dockerfiles')
    for name in os.listdir(base_path):
        full_path = os.path.join(base_path, name)
        if not name.startswith('.') and os.path.isdir(full_path):
            tag = 'system/%s' % name
            local('cd %s && sudo docker build -t="%s" .' % (full_path, tag))


@configuredtask
def install_app_mgmt(compile_base=True):
    compile_base = str(compile_base).lower() in ['true', '1']
    if compile_base:
        build_base()

    export_image('system/redis')
    export_image('system/hipache')

    redis_password = gencode(12)
    redis = run_image('system/redis', PASSWORD=redis_password)
    redis_uri = 'redis://:%s@%s/0' % (redis_password, redis.paths[0])

    hipache = run_image('system/hipache', ports='80:80', REDIS_URI=redis_uri)
    hipache_uri = 'http://' + hipache.paths[0]

    return register_balancer(hipache_uri, redis_uri)
