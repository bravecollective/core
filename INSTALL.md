# Installation of Core

## Create a virtual environment, download sources and install Core

    virtualenv brave
    cd brave
    source bin/activate
    git clone https://github.com/bravecollective/core.git
    cd core
    pip install -r requirements.txt -e .
    python setup.py install

## Edit config
Configuration of Core is located in ``conf/`` directory
Copy the file ``development.ini`` to something like ``production.ini`` and edit it to fit your needs

## Bootstrap the EVE API system

    paster shell conf/local.ini # or don't mention an INI if you didn't customize
    from brave.core.util.eve import populate_calls
    populate_calls()
    from brave.core.permission.controller import init_perms
    init_perms()


# Running Core services
## Set environment variables
Core uses environment variables for parts of configuration

    export CORE_HOME=/home/core/brave/core # location of Core sources
    export CONF_LOCATION=$CORE_HOME/conf/production.ini # location of your config
    export KEY_UPDATE_HOURS=6 # how often you want to update character data from EVE API

## Make sure service files are executable
They should already be executable when cloned from github, but this doesn't hurt

    cd $CORE_HOME/bin
    chmod +x service-*

## Run services

    cd $CORE_HOME/bin
    service-core start

