

Getting started::

    git clone ... dockcluster
    cd dockcluster
    pip install -r requirements.txt
    fab awssetup

Adding an app::

    fab add_app:myapp,https://github.com/username/proj.git
    #TODO: fab add_size:regular,RAM=512,CPU=1
    fab up_app:myapp
    fab update_app:myapp
    fab add_domain:myapp,www.myapp.com

TODO
====

Add a node::

    fab add_size:regular,RAM=512,CPU=1
    fab add_node:regular
    

