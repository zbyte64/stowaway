FROM ubuntu:12.04
MAINTAINER Jason Kraus "jason@montagable.com"
RUN	echo "deb http://archive.ubuntu.com/ubuntu precise main universe" > /etc/apt/sources.list
RUN apt-get -y update
RUN apt-get install -y redis-server python
#ADD ./patches.py /usr/local/bin/patches.py
ADD ./run.sh /usr/local/bin/run.sh
RUN /etc/init.d/redis-server stop

EXPOSE 6379
CMD ["/usr/local/bin/run.sh"]

