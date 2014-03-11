# -*- coding: utf-8 -*-
import os
import urllib2
import yaml

from fabric.api import env, prompt

from stowaway.state import configCollection, boxCollection
from stowaway.utils import GB
from stowaway.commands import load_settings


env.VIRTUAL_BOX = 'http://files.vagrantup.com/precise64.box'


def populate_boxes(environ):
    boxCollection.create(label='vb small', cpu=1, memory=int(1.7 * GB), default=True)


def setupvirtualbox():
    environ = configCollection.get('environ') or dict()
    environ['PROVISIONER'] = 'virtualbox'
    environ['BOX_NAME'] = 'ubuntu'

    configCollection['environ'] = environ

    load_settings()

    populate_boxes(environ)

    env.VAGRANT.box_add('virtualbox', env.VIRTUAL_BOX, provider='virtualbox', force=True)

env.PROVISION_SETUPS['virtualbox'] = setupvirtualbox
