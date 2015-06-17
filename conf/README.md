# Core INI Config Files

Core uses multiple `.ini` files to define config options. Each config file maps to a desired environment. We name the example file `development.ini` because you can freely copy/edit/revert it and pay around with the ini settings.

For production, we default to enforcing a ini file named `production.ini` for all your production settings and options. You are free to name these files however you want, you will just need to update where they are refrenced. You can also make any number of duplicate files and refrence them directly when starting a paster instance. 

    $ paster shell conf/$NAME.ini

## Under construction

We plan to expand greatly on what each config option is and how to set them.