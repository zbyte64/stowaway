Provides fabric commands for deploying docker instances to machines provisioned through vagrant. Uses vagrant-aws to deploy to AWS.


Internal Services
=================

The following services are overhead for orchestraton:

* Redis for state management
* Hipache for load balancing http services
* samalba/docker-registry for pushing locally built apps


Commands
========

Getting started::

    git clone ... dockcluster
    cd dockcluster
    pip install -r requirements.txt
    fab awssetup

Adding an app::

    fab add_app:shipyard,https://github.com/ehazlett/shipyard.git
    #TODO: fab add_size:regular,RAM=512,CPU=1
    fab up_app:shipyard
    fab update_app:shipyard
    fab add_domain:shipyard,www.shipyard.com


TODO
====

Add a node::

    fab add_size:regular,RAM=512,CPU=1
    fab add_node:regular
    

