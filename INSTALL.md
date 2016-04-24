# Installation of Core

## Create a virtual environment, download sources and install Core

    mkdir /home/core
    cd /home/core
    virtualenv brave
    cd brave
    source bin/activate
    git clone https://github.com/bravecollective/core.git
    cd core
    pip install -r requirements.txt -e .
    python setup.py install

## Edit config
Configuration of Core is located in ``bin/``, ``conf/`` and ``etc/`` directory.
Adapt all files as needed.

## Bootstrap the EVE API system

   source ./bin/core-env
   ./bin/core-shell
    from brave.core.util.eve import populate_calls
    populate_calls()
    from brave.core.permission.controller import init_perms
    init_perms()

# Running Core services for development
Make sure you edited ``bin/core-env`` and ``conf/development.ini``.

   source ./bin/core-env
   ./bin/core-serve

# Running Core services for production
Make sure you edited ``bin/core-env``, ``conf/production.ini`` and setup a nginx configuration using ``etc/nginx.conf.off``.

   source ./bin/core-env
   ./bin/service-core start
   ./bin/service-update start
