# Bin Scripts

These scripts are designed to be coppied into you virtualenv's bin folder. Before you do anyhting else, make sure that you are not running these inside this folder.

## service-core

Service management script. This program wil start/stop/restart the core FASTCGI sockets for use in nginx/apache or similar software. Usage is as follows:

    $ service-core start
    $ service-core stop
    $ service-core restart

This script will control the other two scripts in this folder `service-update-chars` and `service-update-keys`, so make sure they are also moved into the virtualenv's bin folder.

## service-update-chars

This script will startup a new paster process that will inteligently distribute public character info api pulls across a given timeframe. The default is 6 hours, so if you have 10,000 character objects that need to be updated this script will update 28 character objects a minute. Eve API calls are cached in mongo so there is no real downside to making this update often, but it should ideally not try to update more then once an hour or sooner then the cache timeouts for public character data, trying to pudate faster then data is allowed to be recached, will result in less data resoloution, you will get a local cache object and wont see new data until the cycle starts over again.

    10000 / 6*60 = 27.777....

## service-update-keys

This does the exact same thing as `service-update-chars`, it just updates API keys and all relevant informtion from them, not public character info.