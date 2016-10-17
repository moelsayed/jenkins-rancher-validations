#!/usr/bin/env python3
# coding: us-ascii
# mode: python

import sys, logging, os, colorama
import requests
from requests import ConnectionError, HTTPError
from invoke import run, Failure
from colorama import Fore
from pprint import pprint as pp
from time import time, sleep


colorama.init()
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
stream = logging.StreamHandler()
stream.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s:%(lineno)s - %(funcName)s - %(message)s'))
log.addHandler(stream)

DOCKER_MACHINE = "docker-machine --storage-path /workdir/.docker/machine "


#
def log_err(msg):
     log.error(Fore.RED + str(msg) + Fore.RESET)


#
def err_and_exit(msg, code=-1):
     log_err(msg)
     sys.exit(-1)


#
def missing_envvars(envvars=['AWS_PREFIX', 'RANCHER_SERVER_OPERATINGSYSTEM']):

     missing = []
     for envvar in envvars:
          if envvar not in os.environ:
               missing.append(envvar)
     log.debug("Missing envvars: {}".format(missing))
     return missing


#
def rancher_server_ip(server_name):
     cmd = DOCKER_MACHINE + " ip {}".format(server_name)
     try:
          result = run(cmd, echo=True)
     except Failure as e:
          log.error("Failed to query the rancher/server address from docker-machine! : {} :: {}".format(e.result.return_code, e.result.stderr))
          return False

     return result.stdout.rstrip()


#
def rancher_server_config_regtoken(server_name):
     url = "http://{}:8080/v2-beta/projects/1a5/registrationtokens".format(server_name)

     start_time = time()
     timeout = 300
     step_time = 5

     while True:
          try:
               resp = requests.post(url, timeout=5)
               log.info("HTTP POST: {}".format(resp.headers))
          except ConnectionError as e:
               log.debug("Failed to connect to \'{}\'! : {}".format(url, e))
               elapsed_time = time() - start_time
               if elapsed_time >= timeout:
                    log.error("Timeout exceeded trying to connect to \'{}\!".format(url))
                    return False
               else:
                    sleep(step_time)
          break

     log.info('Successfully created reg token on rancher/server.')
     return True


#
def rancher_server_config_regURL(server):

     log.info("Configuring rancher/server registration URL...")

     max_attempts = 100
     attempts = 0
     step_time = 10
     post_data = {}

     while attempts <= max_attempts:
          try:
               attempts += 1

               # set the reg command url
               url = "http://{}:8080//v2-beta/settings/api.host".format(server)
               put_data = {"type": "activeSetting",
                           "name": "api.host",
                           "activeValue": '',
                           "inDb": False,
                           "source": "",
                           "value": "http://{}:8080".format(server)}
               log.debug("PUT: {} :: {}".format(url, put_data))
               resp = requests.put(url, put_data, timeout=5)
               log.info("HTTP PUT: {}".format(resp.headers))
               break

          except (HTTPError, ConnectionError) as e:
               log.debug("PUT failed: {} :: {} :: {}".format(url, put_data, e))
               if attempts >= max_attempts:
                    log.error("Exceeded max attempts!".format(url))
                    return False
               sleep(step_time)

     log.info("Successfully set the registration URL to \'http://{}:8080\'".format(server))
     return True


#
def rancher_server_add_ssh_keys(server):
     url = 'https://raw.githubusercontent.com/rancherlabs/ssh-pub-keys/master/ssh-pub-keys/ci'

     server_os = os.environ.get('RANCHER_SERVER_OPERATINGSYSTEM')

     if 'rancher' in server_os:
          cmd = DOCKER_MACHINE + " ssh {} 'wget {} -O - >> ~/.ssh/authorized_keys && chmod 0600 ~/.ssh/authorized_keys'".format(server, url)
     else:
          cmd = DOCKER_MACHINE + " ssh {} 'curl {} >> ~/.ssh/authorized_keys && chmod 0600 ~/.ssh/authorized_keys'".format(server, url)

     try:
          result = run(cmd, echo=True)
     except Failure as e:
          log.error("Failed to download ssh pub keys! :: {} : {}".format(e.result.return_code, e.result.stderr))
          return False

     return True


#
def configure_rancher_server():
     aws_prefix = os.environ.get('AWS_PREFIX')

     server_name = "{}-vtest-server0".format(os.environ.get('RANCHER_SERVER_OPERATINGSYSTEM'))
     if aws_prefix:
          server_name = "{}-".format(aws_prefix) + server_name

     server_address = rancher_server_ip(server_name)
     if server_address is False:
          log.error("Failed getting IP for \'{}\'!".format(server_name))
          return False

     if False is rancher_server_add_ssh_keys(server_name):
          log.error('Failed to populate rancher/server instance with ssh pub keys!')
          return False

     if rancher_server_config_regtoken(server_address) is False:
          log.error("Failed to enable reg token on \'{}\'!".format(server_name))
          return False

     if rancher_server_config_regURL(server_address) is False:
          log.error("Failed to set the agent reg URL on \'{}\'!".format(server_name))
          return False

     return True


#
def main():
     if os.environ.get('DEBUG'):
          log.setLevel(logging.DEBUG)
          log.debug("Environment:")
          log.debug(pp(os.environ.copy(), indent=2, width=1))

     # validate our envvars are in place
     missing = missing_envvars()
     if [] != missing:
          err_and_exit("Unable to find required environment variables! : {}".format(', '.join(missing)))

     if not configure_rancher_server():
          err_and_exit("Failed while configuring rancher/server!")


if '__main__' == __name__:
    main()
