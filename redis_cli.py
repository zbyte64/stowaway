# -*- coding: utf-8 -*-
import redis
import sys


uri = sys.argv[1]
r = redis.StrictRedis.from_url(uri)
print r.execute_command(*sys.argv[2:])
