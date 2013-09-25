import os
import json
import logging

from microcollections.datastores import MemoryDataStore


class JSONFileDataStore(MemoryDataStore):
    def __init__(self, path, prettify=True):
        super(JSONFileDataStore, self).__init__()
        self.path = path
        self.prettify = prettify
        if os.path.exists(path):
            for filename in os.listdir(path):
                fullpath = os.path.join(path, filename)
                if filename.endswith('.json') and os.path.isfile(fullpath):
                    name = filename[:-len('.json')]
                    try:
                        cstore = json.load(open(fullpath, 'r'))
                    except ValueError:
                        logging.exception('Could not load collection: %s' % name)
                    else:
                        self.collections[name] = cstore
        else:
            os.makedirs(path)

    def execute_hooks(self, hook, kwargs):
        name = kwargs['collection'].name
        cstore = self._get_cstore(kwargs['collection'])
        ret = super(JSONFileDataStore, self).execute_hooks(hook, kwargs)
        if hook in ['afterSave', 'afterRemove', 'afterDelete']:
            outpath = os.path.join(self.path, name + '.json')
            json_kwargs = dict()
            if self.prettify:
                json_kwargs['indent'] = 4
            json.dump(cstore, open(outpath, 'w'), **json_kwargs)
        return ret
