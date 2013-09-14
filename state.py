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


class AppInstance(micromodels.Model):
    appname = micromodels.CharField()
    node = micromodels.CharField(help_text='Hostname')
    size = micromodels.CharFIeld(required=False)
    container_id = micromodels.CharField(required=False)
    path = micromodels.CharField()


#TODO use redis on cluster
datastore = MemoryDataStore()
sizeCollection = Collection(ContainerSize, datastore=datastore)
nodeCollection = Collection(Node, datastore=datastore)
appCollection = Collection(AppInstance, datastore=datastore)
