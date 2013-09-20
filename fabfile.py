# -*- coding: utf-8 -*
'''
Possible name: stowaway
Idea:

#gets you ready for aws
fab awssetup

#returns node name
fab provision

#returns port listing and a container id
fab run_image:samalba/hipache
fab stop_instance:container_id

#deploy local image
fab export_image:mylocalimage
fab run_image:mylocalimage


#status inspection
fab list_instances(:filter=value)
fab list_nodes(:filter=value)


#for cluster creation
-- compile local dockerfiles --
fab export_image:<system images>
##fab run_image:docker-registry #for when we can lock it down
fab run_image:redis,PASSWORD=r4nd0m
fab run_image:hipache,port=80:80,REDIS_URI=<redis uri with pass>
fab register_balancer:<hipache path>,<redis uri>[,<name>]

fab export_image:<app image>
fab add_app:<name>,<app image>,<balancer>
#set environ, stored in the appCollection
fab app_config:KEY1=VALUE1,KEY2=VALUE2
fab app_remove_config:KEY1,KEY2
#num=-1 to descale
fab app_scale:<name>[,<num=1>,<process>]
fab app_add_domain:<name>,<domain>

'''
import os
import shutil
import re

from vagrant import Vagrant

from fabric.api import env, local, run, put, sudo, prompt, settings
from fabric.context_managers import cd

from .state import nodeCollection, instanceCollection, configCollection, balancerCollection, appCollection


env.AWS_BOX = 'https://github.com/mitchellh/vagrant-aws/raw/master/dummy.box'
env.PROVISIONER = None
env.DOCKER_REGISTRY = None
env.TOOL_ROOT = os.path.split(os.path.abspath(__filename__))[0]
env.WORK_DIR = os.getcwd()
env.VAGRANT = None


class machine(object):
    def __init__(self, name):
        self.name = name
    
    def make_settings_patch(self):
        self.settings_patch = settings(
            host_string = env.VAGRANT.user_hostname_port(vm_name=self.name),
            key_filename = env.VAGRANT.keyfile(vm_name=self.name),
            disable_known_hosts = True)
    
    def __enter__(self):
        self.make_settings_patch()
        self.settings_patch.__enter__()
    
    def __exit__(self):
        self.settings_patch.__exit__()


def setup(workingdir=None):
    shutil.copy(os.path.join(env.TOOL_ROOT, 'Vagrantfile'), 
                env.WORK_DIR)
    env.VAGRANT = Vagrant(env.WORK_DIR)
    #provisioner = prompt('What provision to use? (aws|...)')
    setupaws()


def setupaws():
    environ = dict()
    environ['PROVISIONER'] = 'aws'
    #TODO prompt for
    #23 and 80 are required
    environ['AWS_SECURITY_GROUPS'] = 'dockcluster'
    environ['AWS_AMI'] = 'ami-e1357b88'
    environ['AWS_MACHINE'] = 'm1.small'
    environ['AWS_ACCESS_KEY_ID'] = prompt('Enter your AWS Access Key ID')
    environ['AWS_SECRET_ACCESS_KEY'] = prompt('Enter your AWS Secret Access Key')
    environ['AWS_KEYPAIR_NAME'] = prompt('Enter your AWS Key pair name')
    environ['AWS_SSH_PRIVKEY'] = prompt('Enter your AWS SSH private key path')
    configCollection['environ'] = environ
    
    load_settings()
    
    env.VAGRANT.box_add('awsbox', env.AWS_BOX, provider='aws')


def load_settings():
    environ = configCollection.get('environ') or dict()
    os.environ.update(environ)
    env.update(environ)
    if not env.VAGRANT:
        env.VAGRANT = Vagrant(env.WORK_DIR)


def gencode(length):
    pass


def provision(name=None):
    load_settings()
    if name is None:
        name = gencode(12)
    env.VAGRANT.up(vm_name=name, provider=env.PROVISIONER)
    return nodeCollection.create(
        name=name,
        hostname=env.VAGRANT.hostname(name),    
    )


def set_registry(uri):
    env.DOCKER_REGISTRY = uri
    environ = configCollection.get('environ') or dict()
    environ['DOCKER_REGISTRY'] = uri
    configCollection['environ'] = environ


def export_image(imagename, *names):
    if env.DOCKER_REGISTRY:
        local('sudo docker push %s --registry=%s' % 
            (imagename, env.DOCKER_REGISTRY))
        return
    if not names:
        names = [node.name for node in nodeCollection.all()]
    local('sudo docker export %s > image.tar' % imagename)
    for name in names:
        with machine(name):
            put('image.tar', '~/image.tar')
            sudo('docker import ~/image.tar')


def run_image(imagename, name=None, ports='', memory=256, cpu=1, **envparams):
    ports = ports.split('-')
    memory = memory * (1024 ** 3) #convert MB to Bytes
    if not name:
        for node in nodeCollection.all():
            if node.can_fit(memory=memory, cpu=cpu):
                name = node.name
                break
    assert name, 'Please provision a new node to make room'

    e_args = ' '.join(['-e %s=%s' % (key, value)
        for key, value in envparams.items()])

    p_args = ' '.join(['-p %s' % port
        for port in ports]
    
    args = ('%s %s -m=%s -c=%s' %
        (e_args, p_args, memory, cpu)).strip()

    with machine(name):
        result = sudo('docker run -d %s %s' % (args, imagename))

        container_id = result.strip().rsplit()[-1]
        
        paths = list()
        hostname = env.VAGRANT.hostname(name)
        
        if not ports:
            result = sudo('docker inspect %s' % container_id)
            #TODO
            ports = [result.strip()]
        
        for port in ports:
            uri = '%s:%s' % (hostname, port.split(':')[0])
            paths.append(uri)
        
        return instanceCollection.create({
            machine_name=name,
            image_name=imagename,
            memory=memory,
            cpu=cpu,
            container_id=container_id,
            paths=paths,
        })


def stop_instance(container_id, name=None):
    if not name:
        instance = instanceCollection.get(container_id=container_id)
        name = instance.machine_name
    while machine(name):
        sudo('docker stop %s' % container_id)
    instanceCollection.filter(container_id=container_id).delete()


def shut_it_down(*names):
    if not names:
        names = [node.name for node in nodeCollection.all()]
    for name in names:
        instances = instanceCollection.filter(machine_name=name)
        for instance in instances:
            stop_instance(instance.container_id, name)


def register_balancer(endpoint, redis, name=None):
    if name is None:
        name = gencode(12)
    return balancerCollection.create({
        name=name,
        endpoint_uri=endpoint,
        redis_uri=redis
    })


def add_app(name, imagename, balancername):
    return appCollection.create({
        name=name,
        image_name=imagename,
        balancer_name=balancername
    })
    

def app_config(name, **environ):
    app = appCollection.get(name=name)
    app.environ.update(environ)
    return app.save()


def app_remove_config(name, *keys):
    app = appCollection.get(name=name)
    for key in keys:
        app.environ.pop(environ, None)
    return app.save()

#num=-1 to descale
def app_scale(name, num=1, process=None):
    num = int(num)
    app = appCollection.get(name=name)
    balancer = balancerCollection.get(name=app.balancer_name)
    if num > 0:
        for i in range(num):
            instance = run_image(app.image_name, **app.environ)
            redis_cli(balancer.redis_uri, 'rpush', 'frontend:%s' % name, instance.paths[0])
    elif num < 0:
        instances = iter(instanceCollection.find(image_name=app.image_name))
        for i in range(abs(num)):
            instance = instances.next()
            stop_instance(instance.container_id)


def app_add_domain(name, domain):
    app = appCollection.get(name=name)
    balancer = balancerCollection.get(name=app.balancer_name)
    redis_cli(balancer.redis_uri, 'rpush', 'frontend:%s' % domain, name)


def app_remove_domain(name, domain):
    app = appCollection.get(name=name)
    balancer = balancerCollection.get(name=app.balancer_name)
    #TODO lookup redis docs
    redis_cli(balancer.redis_uri, 'rpop', 'frontend:%s' % domain, name)


def redis_cli(uri, *args):
    #TODO
    return run('python redis-cli.py ' + ' '.join(["%s" % arg for arg in args]))

