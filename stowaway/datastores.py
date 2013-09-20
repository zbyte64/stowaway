import os
import json

from microcollections.datastores import MemoryDataStore


class JSONFileDataStore(MemoryDataStore):
    def __init__(self, path):
        self.path = path
        if os.path.exists(path):
            pass #TODO load
        else:
            os.makedirs(path)

    def execute_hooks(self, hook, kwargs):
        name = kwargs['collection'].name
        ret = super(JSONFileDataStore, self).execute_hooks(hook, kwargs)
        outpath = os.path.join(self.path, name + '.json')
        json.dumps(self.objects[name], open(outpath, 'w'))
        return ret
