# -*- coding: utf-8 -*
import os
from os import environ
import re

from fabric.api import env, local, run, put, sudo, prompt
from fabric.context_managers import cd


env.DOCKER_PROVISION = 'vagrant up'
env.DOCKER_REPOSITORY = 'https://github.com/dotcloud/docker.git'
ENV_LINE = re.compile(r'^([A-Za-z0-9_]+)=\s*(.+)$')
recorded_envs = set()


def vagrant():
    # use vagrant ssh key
    result = local('vagrant ssh-config', capture=True)

    info = dict()
    for line in result.split('\n'):
        line = line.strip()
        if line:
            key, value = line.split(' ', 1)
            info[key] = value

    env.key_filename = info['IdentityFile']
    env.host_string = '%s:%s' % (info['HostName'], info['Port'])
    env.hosts = [env.host_string]
    env.user = info['User']


def aws():
    env.PROVIDER = 'aws'
    environ['BOX_NAME'] = 'awsbox'
    env.DOCKER_PROVISION = 'vagrant up --provider=aws'
    result = local('vagrant box list', capture=True)
    if 'awsbox' not in result:
        local('vagrant box add awsbox https://github.com/mitchellh/vagrant-aws/raw/master/dummy.box')
    result = local('vagrant status', capture=True)
    if 'default' in result and 'running' in result:
        vagrant()

def load_settings(path=None):
    env.update(environ)
    if not path:
        path = environ.get('DOCKCLUSTER_ENV', '.env')
    if os.path.exists(path):
        for line in open(path, 'r').readlines():
            m = ENV_LINE.match(line)
            if m:
                recorded_envs.add(m.group(1).strip())
                environ[m.group(1).strip()] = m.group(2).strip()
        env.update(environ)
        if env.get('PROVISIONER') == 'aws':
            aws()
        else:
            vagrant()


def write_settings(path=None):
    if not path:
        path = environ.get('DOCKCLUSTER_ENV', '.env')
    outfile = open(path, 'w')
    for key in recorded_envs:
        outfile.write('%s=%s\n' % (key, env.get(key)))
    outfile.close()


def gencode(length):
    pass


def awssetup():
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
    env.update(environ)
    recorded_envs.update(['PROVISIONER', 'AWS_ACCESS_KEY_ID', 'AWS_AMI',
        'AWS_SECRET_ACCESS_KEY', 'AWS_KEYPAIR_NAME', 'AWS_SSH_PRIVKEY',
        'AWS_SECURITY_GROUPS', 'AWS_MACHINE'])
    write_settings()
    aws()
    provision()
    initialize()


def provision():
    local('%(DOCKER_PROVISION)s' % env)


#TODO make this into a privileged Dockerfile
def initialize():
    #provision and install docker
    #provision()
    #print 'Provision result:', result
    vagrant()  # load connection info
    #copy self
    for app in ['image_store', 'redis', 'hipache']:
        run('mkdir -p ~/dockcluster/%s' % app)
        put('%s/*' % app, '~/dockcluster/%s' % app)
    run('mkdir -p ~/apps')
    #sudo('apt-get update')
    sudo('apt-get install -q -y git-core')

    for app in ['image_store', 'redis', 'hipache']:
        with cd('dockcluster/' + app):
            sudo('docker build -t=sys/%s .' % app)

    #TODO set password or tunnel to redis
    up_sys('redis', '6379:6379', {'REDIS_PASSWORD': gencode(12)})
    env.REDIS_URI = 'redis://localhost:6379'

    #TODO mount ssl cert to /etc/ssl/ssl.(crt|key)
    #TODO internode should be ssl, fetch from /etc/ssl/ssl.crt
    up_sys('hipache', '80:80', {'REDIS_URI': env.REDIS_URI})
    env.HIPACHE_URI = 'http://localhost:80'

    #TODO make ssl with private ip
    #TODO maintain list of accepted root certs from deployed instances
    up_sys('image_store', '4990:5000')
    env.IMAGESTORE_URI = 'http://localhost:4990'

    recorded_envs.update(['REDIS_URI', 'HIPACHE_URI', 'IMAGESTORE_URI'])

    for app in ['image_store', 'redis', 'hipache']:
        with cd('dockcluster/' + app):
            sudo('docker push %%(IMAGESTORE_URI)s/sys/%s' % app % env)

    write_settings()


def up_sys(appname, port=None, environ={}):
    return up_app(appname, port, environ, True)


def up_app(appname, port=None, environ={}, system=False):
    if system:
        appname = 'sys/%s' % appname
    else:
        appname = 'app/%s' % appname
    #TODO select node
    node = 'localhost'
    e_args = ' '.join(['-e %s=%s' % (key, value)
        for key, value in environ.items()])
    if port:
        result = sudo('docker run -d -p %s %s %s' % (port, e_args, appname))
    else:
        result = sudo('docker run -d %s %s' % (e_args, appname))
        #TODO parse port

    container_id = result.strip().rsplit()[-1]
    print 'docker run result:', container_id, '\n', result
    uri = '%s:%s' % (node, port)

    #from .state import appCollection
    #appCollection.create(appname=appname, path=uri, node=node) #size, container_id

    if not system:
        join_mesh(appname, uri)
    return uri


def join_mesh(appname, endpoint):
    #TODO https all internal traffic
    #install ssl, and make it talk only to hipache's cert
    sudo('redis-cli rpush frontend:%s http://%s' % (appname, endpoint))


def add_app(appname, giturl):
    #use plain docker for now, a githook can always add it before calling this
    with cd('apps'):
        run('git clone %s %s' % (giturl, appname))
        with cd(appname):
            sudo('docker build -t=app/%s .' % appname)
            sudo('docker push %%(IMAGESTORE_URI)s/app/%s' % appname % env)


def update_app(appname):
    with cd('apps/%s' % appname):
        run('git pull')
        sudo('docker build -t=app/%s .' % appname)
        sudo('docker push %%(IMAGESTORE_URI)s/app/%s' % appname % env)
    #TODO update app instances
    #from .state import appCollection
    #for instance in appCollection[appname]


def add_domain(appname, domain):
    sudo('redis-cli rpush frontend:%s http://%s' % (domain, appname))


def remove_domain(appname, domain):
    #TODO lookup redis docs
    sudo('redis-cli rpop frontend:%s http://%s' % (domain, appname))


load_settings()
