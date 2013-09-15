FROM base
MAINTAINER Jason Kraus "jason@montagable.com"
RUN apt-get -qq update
RUN apt-get install -y redis-server
ADD ./redis.conf /etc/redis/redis.conf

EXPOSE 6379
CMD ["/usr/bin/redis-server", "/etc/redis/redis.conf"]
