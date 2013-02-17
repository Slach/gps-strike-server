## GPS Strike Server
server sources of simple

## Prepare server

* sudo aptitude install python-virtualenv python-pip
* sudo mkdir /opt
* cd /opt
* sudo virtualenv gps-strike
* sudo ./gps-strike/bin/pip install sockjs-tornado
* sudo chown -R ubuntu:ubuntu /opt/gps-strike

## Deploy last source version with fabric
* git clone git@github.com:Slach/gps-strike-server.git ./
* change fabfile.py env.roledefs
* fab -u username -p passsword deploy


## Prepare configuration file and run on server
* open server.cfg and change options
* cd /opt/gps-strike/current
* ../bin/python run.py
