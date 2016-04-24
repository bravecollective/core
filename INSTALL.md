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
Configuration of Core is located in ``bin/core-env``, ``conf/*.ini`` and ``etc/``.
Copy ``conf/development.ini`` or ``conf/production.ini`` to ``local.ini``.

## Bootstrap the EVE API system

    source ./bin/core-env
    ./bin/core-shell
    from brave.core.util.eve import populate_calls
    populate_calls()
    from brave.core.permission.controller import init_perms
    init_perms()

# Running Core services for development

    source ./bin/core-env
    ./bin/core-serve

# Running Core services for production

    source ./bin/core-env
    ./bin/service-core start
    ./bin/service-update start
