FROM base
MAINTAINER Jason Kraus "jason@montagable.com"
RUN apt-get -qq update
RUN apt-get install -y redis-server python
#ADD ./patches.py /usr/local/bin/patches.py
#ADD ./run.sh /usr/local/bin/run.sh
RUN /etc/init.d/redis-server stop

EXPOSE 6379
CMD ["/usr/bin/redis-server"]
