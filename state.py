# -*- coding: utf-8 -*-
import micromodels
from microcollections.collections import Collection
from microcollections.datastores import MemoryDataStore
import datetime


class ContainerSize(micromodels.Model):
    name = micromodels.CharField()
    memory = micromodels.IntegerField(required=False, help_text='In bytes')
    cpu = micromodels.IntegerField(required=False, help_text='CPU Shares')


class Node(micromodels.Model):
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


class AppInstance(micromodels.Model):
    appname = micromodels.CharField()
    node = micromodels.CharField(help_text='Hostname')
    memory = micromodels.IntegerField(required=False, help_text='In bytes')
    cpu = micromodels.IntegerField(required=False, help_text='CPU Shares')
    container_id = micromodels.CharField(required=False)
    path = micromodels.CharField()


#TODO use redis on cluster
datastore = MemoryDataStore()
sizeCollection = Collection(ContainerSize, datastore=datastore)
nodeCollection = Collection(Node, datastore=datastore)
appCollection = Collection(AppInstance, datastore=datastore)
