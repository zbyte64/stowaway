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
* micromodels
* micromodels-collections


Commands
========

Getting started::

    pip install stowaway
    mkdir mydockercluster && cd mydockercluster
    stowaway embark

    #returns node name
    stowaway provision

    #returns port listing and a container id
    stowaway run_image:samalba/hipache
    stowaway stop_instance:container_id

    #deploy local image
    stowaway export_image:mylocalimage
    stowaway run_image:mylocalimage


    #status inspection
    stowaway list_instances
    stowaway list_nodes


    #for cluster creation
    stowaway install_app_mgmt
    
    #or do it manually:
    stowaway build_base
    stowaway export_image:sys/redis
    stowaway export_image:sys/hipache
    stowaway run_image:sys/redis,PASSWORD=r4nd0m
    stowaway run_image:sys/hipache,ports=80:80,REDIS_URI=<redis uri with pass>
    stowaway register_balancer:<hipache path>,<redis uri>[,<name>]

    #now add apps and manage them
    stowaway export_image:<app image>
    stowaway add_app:<name>,<app image>,<balancer>
    #configure app environ
    stowaway app_config:KEY1=VALUE1,KEY2=VALUE2
    stowaway app_remove_config:KEY1,KEY2
    #num=-1 to descale
    stowaway app_scale:<name>[,<num=1>,<process>]
    stowaway app_add_domain:<name>,<domain>

