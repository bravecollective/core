# -*- mode: ruby -*-

$bootstrap = <<SHELLSCRIPT

# Install Mongo
sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 7F0CEB10
echo 'deb http://downloads-distro.mongodb.org/repo/ubuntu-upstart dist 10gen' | sudo tee /etc/apt/sources.list.d/mongodb.list
sudo apt-get update
sudo apt-get -y install mongodb-10gen

sudo apt-get -y install python-pip python-dev python-lxml python-virtualenv python-software-properties

# Python package manager
sudo pip install setuptools --upgrade
sudo pip install pip --upgrade

# Set up Python environment
virtualenv --system-site-packages /home/vagrant/core-env
echo "source /home/vagrant/core-env/bin/activate" >> /home/vagrant/.profile
source /home/vagrant/core-env/bin/activate
cd /vagrant
python setup.py develop

# Final tweaks
if [ ! -f /vagrant/local.ini ]; then
  cp /vagrant/conf/development.ini /vagrant/local.ini
fi
echo 'alias serve="paster serve --reload /vagrant/local.ini"' >> /home/vagrant/.profile
echo 'echo "To start the server, type serve"' >> /home/vagrant/.profile

SHELLSCRIPT

# Vagrantfile API/syntax version. Don't touch unless you know what you're doing!
VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.vm.box = "hashicorp/precise32"
  
  config.vm.provision "shell", privileged: false, inline: $bootstrap
  
  config.vm.network "forwarded_port", guest: 8080, host: 8080
end
