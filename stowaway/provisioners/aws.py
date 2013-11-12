# -*- coding: utf-8 -*-
import os
import urllib2
import yaml

from fabric.api import env, prompt

from stowaway.state import configCollection, boxCollection
from stowaway.utils import GB
from stowaway.commands import load_settings


env.AWS_BOX = 'https://github.com/mitchellh/vagrant-aws/raw/master/dummy.box'


def populate_boxes(environ):
    boxCollection.create(label='small', cpu=1, memory=int(1.7 * GB), params={
        'AWS_AMI': environ['AWS_AMI'],
        'AWS_MACHINE': 'm1.small',
    },)
    boxCollection.create(label='medium', cpu=2, memory=int(3.75 * GB), params={
        'AWS_AMI': environ['AWS_AMI'],
        'AWS_MACHINE': 'm1.medium',
    }, default=True)
    boxCollection.create(label='large', cpu=4, memory=int(7.5 * GB), params={
        'AWS_AMI': environ['AWS_AMI'],
        'AWS_MACHINE': 'm1.large',
    },)


def get_available_amis(environ, filters):
    resp = urllib2.urlopen('http://cloud-images.ubuntu.com/locator/ec2/releasesTable')
    data = yaml.load(resp.read())
    entries = data.values()[0]
    columns = ['zone', 'name', 'version', 'arch', 'instance type', 'release',
               'AMI-ID', 'AKI-ID']
    amis = list()
    for entry in entries:
        row = dict(zip(columns, entry))
        row['AMI-ID'] = row['AMI-ID'].split('>', 1)[1].split('<', 1)[0]
        match = True
        for key, val in filters.items():
            rval = row[key]
            if callable(val):
                match = val(rval)
            else:
                match = rval == val
            if not match:
                break
        if match:
            amis.append(row)
    return amis


def setupaws():
    environ = configCollection.get('environ') or dict()
    environ['PROVISIONER'] = 'aws'
    environ['BOX_NAME'] = 'awsbox'

    environ['AWS_ACCESS_KEY_ID'] = prompt('Enter your AWS Access Key ID')
    environ['AWS_SECRET_ACCESS_KEY'] = prompt('Enter your AWS Secret Access Key')

    #ports 23 and 80 are required
    environ['AWS_SECURITY_GROUPS'] = prompt('Enter AWS security group', default='dockcluster')
    #TODO list regions
    environ['AWS_REGION'] = prompt('Enter AWS region', default='us-east-1')

    #prompt ami based on region
    filters = {
        'zone': environ['AWS_REGION'],
        'arch': 'amd64',
        'instance type': 'instance-store',
        'version': '12.04 LTS',
    }
    amis = get_available_amis(environ, filters)
    environ['AWS_AMI'] = prompt('Enter AWS AMI (%s)' % ','.join([ami['AMI-ID'] for ami in amis]),
        default=amis[0]['AMI-ID'])
    #environ['AWS_MACHINE'] = prompt('Enter AWS Machine Size', default='m1.small')
    environ['AWS_KEYPAIR_NAME'] = prompt('Enter your AWS Key pair name')
    default_pem_path = os.path.join(os.path.expanduser('~/.ssh'), environ['AWS_KEYPAIR_NAME'] + '.pem')
    environ['AWS_SSH_PRIVKEY'] = prompt('Enter your AWS SSH private key path', default=default_pem_path)
    configCollection['environ'] = environ

    load_settings()

    populate_boxes(environ)

    env.VAGRANT.box_add('awsbox', env.AWS_BOX, provider='aws', force=True)

env.PROVISION_SETUPS['aws'] = setupaws
