# -*- coding: utf-8 -*-
from fabric.api import env, local, run, put, sudo
from fabric.context_managers import cd, shell_env


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
    #TODO verify:
    #export AWS_ACCESS_KEY_ID=xxx
    #export AWS_SECRET_ACCESS_KEY=xxx
    #export AWS_KEYPAIR_NAME=xxx
    #export AWS_SSH_PRIVKEY=xxx
    env.DOCKER_PROVISION = 'vagrant up --provider=aws'


collectionMaker = None
nodeCollection = None
appCollection = None


def initialize():
    #provision with docker
    local('cd %(DOCKER_PATH)s &&  %(DOCKER_PROVISION)s')
    #copy self
    put('.', '/opt/dockcluster')
    run('mkdir apps')
    #sudo('apt-get update')
    sudo('apt-get install redis-server') #purely for redis-cli

    for app in ['image_store', 'redis', 'hipache']:
        with cd('/opt/dockcluster/' + app):
            sudo('docker build -t %s.' % app)

    env.REDIS_URI = 'redis://%%(HOST)s/%s' % up_sys('redis', 6379) % env
    env.HIPACHE_URI = 'https://%%(HOST)s/%s' % up_sys('hipache', 443,
        {'REDIS_URI': env.REDIS_URI}) % env
    env.IMAGESTORE_URI = 'https://%%(HOST)s/%s' % up_sys('image_store') % env

    for app in ['image_store', 'redis', 'hipache']:
        with cd(app):
            sudo('docker push %s %(IMAGESTORE_URI)s' % app)

    print 'Resulting env:', env.IMAGESTORE_URI, env.REDIS_URI, env.HIPACHE_URI
    #TODO write to env


def up_sys(appname, port=None, environ={}):
    up_app(appname, port, environ, True)


def up_app(appname, port=None, environ={}, system=False):
    #TODO select node
    if not system:
        appname = 'app-%s' % appname
    node = 'localhost'
    with shell_env(**environ):
        if port:
            sudo('docker run %s %s' % (appname, port), capture=True)
        else:
            result = sudo('docker run %s' % appname, capture=True)
            #TODO
            port = result.split()[1]
    #TODO update appCollection
    #appCollection[appname].instances.add(uri)
    uri = '%s:%s' % (node, port)
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
            sudo('docker push app-%s %(IMAGESTORE_URI)s' % appname)
    #appCollection['app-%' % appname]


def update_app(appname):
    with cd('apps/%s' % appname):
        run('git pull')
        sudo('docker build -t=app-%s .' % appname)
        sudo('docker push app-%s %(IMAGESTORE_URI)s' % appname)
    #TODO update app instances
    #for instance in appCollection[appname]


def add_domain(appname, domain):
    sudo('redis-cli rpush frontend:%s http://%s' % (domain, appname))


def remove_domain(appname, domain):
    #TODO lookup redis docs
    sudo('redis-cli rpop frontend:%s http://%s' % (domain, appname))
