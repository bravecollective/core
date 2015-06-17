# Nginx Config

We include a sample nginx config here to help you get started with a proper production hosting setup. The bin scripts 
will create 2 flup FASTCGI sockets into core, which we use to process requests. These are plain unix sockets for 
raw speed. If you have followed the recommended install procedures and/or ran the bootstrap setup script, you should 
already have all the files in the right place, and you should not need to edit this file much. 

We recommend configuring nginx to autoload nginx conf files based on a glob include like this:

    http {
        ...
        include /home/*/etc/nginx.conf;
        include /www/*/etc/nginx.conf;
    }

This will allow you to package up your virtualenv as a self contained application bundle, with everything needed to 
run core contained inside it. This has numerous advantages, ease of backups, easy of maintenance, etc. If you do 
something like the above, all you have to do is ensure that there is a valid nginx.conf file in the right place and 
restart nginx. Ideally everything should just work^tm