# -*- coding: utf-8 -*-
import os
import datetime

import micromodels
from microcollections.collections import Collection, RawCollection

from .datastores import JSONFileDataStore


class Node(micromodels.Model):
    name = micromodels.CharField()
    hostname = micromodels.CharField()
    created = micromodels.DateTimeField(default=datetime.datetime.now)
    memory_capacitiy = micromodels.IntegerField(required=False, help_text='In bytes')
    cpu_capacity = micromodels.IntegerField(required=False, help_text='CPU Shares')

    def get_instances(self):
        return appCollection.find(node=self.hostname)

    def can_fit(self, memory, cpu):
        instances = self.get_instances()

        for instance in instances:
            memory += instance.memory or 0

        for instance in instances:
            cpu += instance.cpu or 0

        if self.memory_capacity and self.memory_capacity < memory:
            return False

        if self.cpu_capacity and self.cpu_capacity < cpu:
            return False

        return True


class DockerInstance(micromodels.Model):
    machine_name = micromodels.CharField()
    image_name = micromodels.CharField()
    memory = micromodels.IntegerField(required=False, help_text='In bytes')
    cpu = micromodels.IntegerField(required=False, help_text='CPU Shares')
    container_id = micromodels.CharField(required=False)
    paths = micromodels.FieldCollection(micromodels.CharField())


class AppInstance(DockerInstance):
    appname = micromodels.CharField()


class Balancer(micromodels.Model):
    name = micromodels.CharField()
    endpoint_uri = micromodels.CharField()
    redis_uri = micromodels.CharField()


class Application(micromodels.Model):
    name = micromodels.CharField()
    image_name = micromodels.CharField()
    balancer_name = micromodels.CharField()
    #environ = micromodels.PrimitiveField(default=dict)


datastore = JSONFileDataStore(path=os.path.join(os.getcwd(), 'db.json'))
nodeCollection = Collection(Node, datastore=datastore)
instanceCollection = Collection(DockerInstance, datastore=datastore)
configCollection = RawCollection(name='config', datastore=datastore)
balancerCollection = Collection(Balancer, datastore=datastore)
appCollection = Collection(Application, datastore=datastore)

