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
    # change from the default user to 'vagrant'
    env.user = 'vagrant'
    # connect to the port-forwarded ssh
    env.hosts = ['127.0.0.1:2222']

    # use vagrant ssh key
    if env.get("PROVIDER"):
        result = local('vagrant ssh_config --provider=%s | grep IdentityFile' % env.PROVIDER, capture=True)
    else:
        result = local('vagrant ssh_config | grep IdentityFile', capture=True)
    env.key_filename = result.split()[1]


def aws():
    env.PROVIDER = 'aws'
    vagrant()
    env.DOCKER_PROVISION = 'vagrant up --provider=aws'


def load_settings(path=None):
    env.update(environ)
    if not path:
        path = environ.get('DOCKCLUSTER_ENV', '.env')
    if os.path.exists(path):
        for line in open(path, 'r').readlines():
            m = ENV_LINE.match(line)
            if m:
                recorded_envs.add(m.group(1))
                environ[m.group(1)] = m.group(2)
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
        outfile.write('%s= %s' % (key, env.get(key)))
    outfile.close()


def gencode(length):
    pass


def awssetup():
    environ['PROVISIONER'] = 'aws'
    environ['AWS_ACCESS_KEY_ID'] = prompt('Enter your AWS Access Key ID')
    environ['AWS_SECRET_ACCESS_KEY'] = prompt('Enter your AWS Secret Access Key')
    environ['AWS_KEYPAIR_NAME'] = prompt('Enter your AWS Key pair name')
    environ['AWS_SSH_PRIVKEY'] = prompt('Enter your AWS SSH private key path')
    env.update(environ)
    recorded_envs.update(['PROVISIONER', 'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY', 'AWS_KEYPAIR_NAME', 'AWS_SSH_PRIVKEY'])
    write_settings()
    aws()
    initialize()


def initialize():
    if 'DOCKER_PATH' not in env:
        if not os.path.exists('docker'):
            local('git clone %(DOCKER_REPOSITORY)s docker' % env)
        env.DOCKER_PATH = './docker'
        recorded_envs.add('DOCKER_PATH')
    #provision with docker
    local('cd %(DOCKER_PATH)s &&  %(DOCKER_PROVISION)s' % env)
    #copy self
    put('.', '/opt/dockcluster')
    run('mkdir apps')
    #sudo('apt-get update')
    sudo('apt-get install redis-server') #purely for redis-cli

    for app in ['image_store', 'redis', 'hipache']:
        with cd('/opt/dockcluster/' + app):
            sudo('docker build -t %s.' % app)

    #TODO set password or tunnel to redis
    env.REDIS_URI = 'redis://%%(HOST)s/%s' % up_sys('redis', 6379,
        {'REDIS_PASSWORD':gencode(12)}) % env
    #TODO mount ssl cert
    env.HIPACHE_URI = 'https://%%(HOST)s/%s' % up_sys('hipache', '80 443',
        {'REDIS_URI': env.REDIS_URI}) % env
    env.IMAGESTORE_URI = 'https://%%(HOST)s/%s' % up_sys('image_store') % env

    recorded_envs.update(['REDIS_URI', 'HIPACHE_URI', 'IMAGESTORE_URI'])

    for app in ['image_store', 'redis', 'hipache']:
        with cd(app):
            sudo('docker push %s %(IMAGESTORE_URI)s' % app)

    write_settings()


def up_sys(appname, port=None, environ={}):
    up_app(appname, port, environ, True)


def up_app(appname, port=None, environ={}, system=False):
    if not system:
        appname = 'app-%s' % appname
    #TODO select node
    node = 'localhost'
    e_args = ' '.join(['-e=%s=%s' % (key, value)
        for key, value in environ.items()])
    if port:
        result = sudo('docker run %s -p=%s %s' % (appname, port, e_args), capture=True)
    else:
        result = sudo('docker run %s %s' % (appname, e_args), capture=True)
        #TODO parse port
    #TODO parse container id
    print 'docker run result:', result
    uri = '%s:%s' % (node, port)

    from .state import appCollection
    appCollection.create(appname=appname, path=uri, node=node) #size, container_id

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
            sudo('docker build -t=app-%s .' % appname)
            sudo('docker push app-%s %%(IMAGESTORE_URI)s' % appname % env)


def update_app(appname):
    with cd('apps/%s' % appname):
        run('git pull')
        sudo('docker build -t=app-%s .' % appname)
        sudo('docker push app-%s %%(IMAGESTORE_URI)s' % appname % env)
    #TODO update app instances
    #from .state import appCollection
    #for instance in appCollection[appname]


def add_domain(appname, domain):
    sudo('redis-cli rpush frontend:%s http://%s' % (domain, appname))


def remove_domain(appname, domain):
    #TODO lookup redis docs
    sudo('redis-cli rpop frontend:%s http://%s' % (domain, appname))


load_settings()
