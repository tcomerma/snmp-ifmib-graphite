#!/usr/bin/env python2.7

import os
import sys
import getopt

CONFIG_PATH = '/etc/snmp-poller'

dir = os.path.join(os.path.dirname(__file__), 'src')
sys.path.insert(0, dir)

import time
from SNMPPoll.daemon import Daemon
from SNMPPoll import logger
from SNMPPoll import snmppoll


class SNMPDaemon(Daemon):
    def __init__(self, pid, config_dir):
        self.config_dir = config_dir
        self.pid = pid
        Daemon.__init__(self, pid)

    def run(self):
        snmppoll.run(self.config_dir)

def usage(cmd):
    print "usage: %s start|stop|restart|debug [-c <config_dir>] [-h]" % sys.argv[0]


if __name__ == "__main__":

    # Arguments parsing
    try:
      opts, args = getopt.gnu_getopt(sys.argv[1:],"hc:")
    except getopt.GetoptError:
      print "Invalid arguments"
      usage(sys.argv[0])
      sys.exit(4)
    for opt, arg in opts:
      if opt == '-h':
         usage(sys.argv[0])
         sys.exit()
      elif opt == '-c':
          CONFIG_PATH = arg

    log = logger.setLogger (CONFIG_PATH)
    daemon = SNMPDaemon('/tmp/snmp-poller.pid', CONFIG_PATH)
    # Processing command
    if len(args) == 1:
        if 'start' == args[0]:
            log.warning('WARNING - Starting daemon.')
            daemon.start()
        elif 'stop' == args[0]:
            log.warning('WARNING - Stopping daemon')
            daemon.stop()
        elif 'restart' == args[0]:
            log.warning('WARNING - Restarting daemon.')
            daemon.restart()
        elif 'debug' == args[0]:
            log.warning('WARNING - Running single debug run')
            daemon.run()
        else:
            print "Unknown command"
            usage(sys.argv[0])
            sys.exit(2)
        sys.exit(0)
    else:
        usage(sys.argv[0])
        sys.exit(3)
