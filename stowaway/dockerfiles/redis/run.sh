#!/bin/bash

echo "requirepass $PASSWORD" >> /etc/redis/redis.conf

redis-server /etc/redis/redis.conf

