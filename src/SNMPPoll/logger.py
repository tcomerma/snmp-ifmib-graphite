import os
import logging
import logging.handlers
import yaml


def setLogger(CONFIG_PATH):
        try:
            with open(CONFIG_PATH + '/snmp-poller.yml') as f:
                LOG_PATH = yaml.load(f)['logging']['path']
        except:
            LOG_PATH = '~/.snmp-poller'
        try:
            with open(CONFIG_PATH + '/snmp-poller.yml') as f:
                LOG_LEVEL = yaml.load(f)['logging']['level']
        except:
            LOG_LEVEL = 'debug'

        if not os.path.exists(LOG_PATH):
            os.makedirs(LOG_PATH)

        format = logging.Formatter('%(asctime)s: %(message)s')
        log_file = os.path.join(os.path.expanduser(LOG_PATH), 'snmp-poller.log')
        mylogger = logging.getLogger('snmp-poller')
        #logger.setLevel(logging.DEBUG)
        mylogger.setLevel(logging.INFO)
        handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=500000,
            backupCount=5)
        handler.setFormatter(format)
        mylogger.addHandler(handler)
        # Adjusting log level
        try:
            log_levels = {'critical': logging.CRITICAL,
                          'error': logging.ERROR,
                          'warning': logging.WARNING,
                          'info': logging.INFO,
                          'debug': logging.DEBUG
                          }
            mylogger.setLevel(log_levels[ LOG_LEVEL ])
        except:
            mylogger.critical ('CRITICAL: Invalid log level in config file')

        return mylogger
