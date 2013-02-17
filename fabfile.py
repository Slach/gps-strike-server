# -*- coding: utf-8 -*-
from __future__ import with_statement
from fabric.api import *
import datetime
import time

env.roledefs = {
    'game': ['game.gps-strike.com'],
}

def load_version():
    f = open('version','rb')
    version = f.readline()
    f.close()
    homedir = '/opt/gps-strike/%s' % (version)
    return (version, homedir)

def update_version():
    version = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d-%H%M%S')
    f = open('version', 'wb')
    f.write(version)
    f.close()
    print "save %s to version file" % (version)

def git_pull():
    local('git pull git@github.com:Slach/gps-strike-server.git master')


def git_push():
    local('git add -A')
    with settings(warn_only=True):
        local('git commit -a -m "deploy version %s"' % ( version ))
        local('git push git@github.com:LinguaLeo/analytics.git master')

def upload_source():
    sudo('mkdir -p -m 0755 %s' % (homedir))
    sudo('mkdir -p -m 0777 /var/log/')
    put('*', homedir, use_sudo=True, mode=0755)
    put('*/*', homedir, use_sudo=True, mode=0755)
    sudo('rm -rfv %s/*.pyc' % (homedir))
    sudo('chmod 0755 %s/*.py' % (homedir))
    sudo('chown -R ubuntu:ubuntu %s' % (homedir))

def relink():
    sudo('rm -vf /opt/gps-strike/current')
    sudo('ln -s %s /opt/gps-strike/current' % (homedir))


@roles('game')
def deploy():
    git_pull()
    upload_source()
    relink()
    git_push()


(version, homedir) = load_version()
print version
print homedir
