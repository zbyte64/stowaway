#!/bin/python
# -*- coding: utf-8 -*-
import os
import json
import subprocess
from urlparse import urlparse, uses_netloc


PATH = '/usr/local/lib/node_modules/hipache/config/config.json'
config = json.load(open(PATH, 'r'))

if 'REDIS_URI' in os.environ:
    uses_netloc.append('redis')
    url = urlparse(os.environ['REDIS_URI'])

    config["redisHost"] = url.hostname
    config["redisPort"] = int(url.port)
    if url.password:
        config["redisPassword"] = url.password

json.dump(config, open(PATH, 'w'))

subprocess.call(["supervisord", "-n"])
