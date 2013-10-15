Stowaway gives simple docker image deployment through vagrant provisioned machines.

Uses vagrant-aws to deploy to AWS.


Application Management
======================

In addition to deploying docker images stowaway provides services for managing applications.

Services used for application management:

* Redis for routing state
* Hipache for load balancing http services


Requirements
============

* fabric
* python-vagrant
* micromodels-ng
* microcollections


Commands
========

Install::

    pip install stowaway


Create a new cluster::

    #create a directory to hold your cluster's state and config
    mkdir mydockercluster && cd mydockercluster
    
    #installs a local docker registry
    stowaway install_local_registry
    
    #will ask configuration questions
    stowaway embark

    #provision a node
    stowaway provision


Upload and run a docker image::

    stowaway export_image:mylocalimage
    stowaway run_image:mylocalimage


See what makes up your cluster::

    stowaway list_instances
    stowaway list_nodes


Install and configure application management::

    #for cluster creation
    stowaway install_app_mgmt
    
    #or do it manually:
    stowaway build_base
    stowaway export_image:sys/redis
    stowaway export_image:sys/hipache
    stowaway run_image:sys/redis,PASSWORD=r4nd0m
    stowaway run_image:sys/hipache,ports=80:80,REDIS_URI=redis://:r4nd0m@ip/0
    stowaway register_balancer:<hipache path>,<redis uri>[,<name>]


Adding and managing apps in the cluster::

    #now add apps and manage them
    stowaway export_image:<app image>
    stowaway add_app:<name>,<app image>,<balancer>
    #configure app environ
    stowaway app_config:KEY1=VALUE1,KEY2=VALUE2
    stowaway app_remove_config:KEY1,KEY2
    #num=-1 to descale
    stowaway app_scale:<name>[,<num=1>,<process>]
    stowaway app_add_domain:<name>,<domain>

