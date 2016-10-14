import time
import socket
import re
import sys
import traceback
import logging


from snimpy.snmp import SNMPException
from snimpy.manager import Manager
from snimpy.manager import load
from SNMPPoll import config
#from SNMPPoll import logger, config


log = None

def poll_interface(m, path, iface, index, alias, metrics):
    '''Gets information for a single interface
    :iface: interface
    '''
    TIMESTAMP = int(time.time())
    iface_name = normalize_ifname(str(iface))
    ts = []
    for metric in metrics:
        valid_metric=False
        if isinstance (metric, list):
            met = metric[0]
            name = metric[1]
        else:
            met = name = metric
        if met == 'ifHCOutOctets':
            valid_metric=True
            v = int(m.ifHCOutOctets[index])
        if met == 'ifHCInOctets':
            valid_metric=True
            v = int(m.ifHCInOctets[index])
        if met == 'ifHighSpeed':
            valid_metric=True
            v = int(m.ifHighSpeed[index])
        if met == 'ifHCInMulticastPkts':
            valid_metric=True
            v = int(m.ifHCInMulticastPkts[index])
        if met == 'ifHCOutMulticastPkts':
            valid_metric=True
            v = int(m.ifHCOutMulticastPkts[index])
        if met == 'ifHCInBroadcastPkts':
            valid_metric=True
            v = int(m.ifHCInBroadcastPkts[index])
        if met == 'ifHCOutBroadcastPkts':
            valid_metric=True
            v = int(m.ifHCOutBroadcastPkts[index])
        if met == 'ifInDiscards':
            valid_metric=True
            v = int(m.ifInDiscards[index])
        if met == 'ifOutDiscards':
            valid_metric=True
            v = int(m.ifOutDiscards[index])
        if met == 'ifInErrors':
            valid_metric=True
            v = int(m.ifInErrors[index])
        if met == 'ifOutErrors':
            valid_metric=True
            v = int(m.ifOutErrors[index])
        if met == 'ifHCInUcastPkts':
            valid_metric=True
            v = int(m.ifHCInUcastPkts[index])
        if met == 'ifHCOutUcastPkts':
            valid_metric=True
            v = int(m.ifHCOutUcastPkts[index])
        if valid_metric:
            p = '%s.%s.%s' % (path, iface_name, name)
            ts.append ('%s %s %s' % (p, v, TIMESTAMP))
        else:
            log.warning("Invalid metric: " + met)
    return (ts)

def poll_device(ip, snmp_community, snmp_version, path, metrics, interfaces='all'):
    '''Using SNMP, polls single device for ifMIB returning tuple for graphite.
    :param ip: ip of the device
    :type ip: str
    :param snmp_community: SNMP community that allows ifMIB values to be read
    :type snmp_community: str
    :param snmp_version: version of SNMP device supports
    :type snmp_version: int
    :param path: desired graphite path for device
    :type path: str
    :param interfaces: **ifName** of interfaces to poll. Careful because this
                       value can be different even within the same vendor.
                       Cisco ASA will return full iface name while IOS abbrev.
    :type interfaces: list of strings or single str 'all'.
    '''
    NULL_IFS = [
        'Nu0',
        'NV0',
        ]
    CARBON_STRINGS = []
    if snmp_version == 2:
        load('SNMPv2-MIB')
        load('IF-MIB')
        try:
            m = Manager(
                host=ip, community=snmp_community, version=snmp_version
                )
        except socket.gaierror, error:
            log.error('SNMP: Error raised for host: %s - %s', ip, error)
    else:
        log.error('SNMP: Version not supported for host: %s', ip)
        return False
    try:
        str(m.sysDescr)
    except SNMPException:
        log.error('SNMP: Cannot poll host: %s - Is it restricted?', ip)
        return False
    if str(interfaces[0]) == 'all':
        log.debug('Polling for all interfaces')
        for iface in m.ifIndex:
            log.debug('Polling for interface: %s [%s]', m.ifName[iface], iface)
            if str(m.ifAdminStatus[iface]) == 'up(1)' and \
                    str(m.ifName[iface]) not in NULL_IFS:
                CARBON_STRINGS.extend(poll_interface (m, path, m.ifName[iface], iface, m.ifName[iface], metrics))
    else:
        if isinstance(interfaces, basestring):
            interface_tmp = interfaces
            interfaces = []
            interfaces.append(interface_tmp)
        elif isinstance(interfaces, list):
            # Split name and alias
            ifnames=[]
            ifalias=[]
            for i in interfaces:
                if isinstance (i,list):
                    ifnames.append(i[0])
                    ifalias.append(i[1])
                else:
                    ifnames.append(i)
                    ifalias.append(i)
            if_indexes=[]
            for k, v in m.ifName.iteritems():
                for i in range (0, len (ifnames)):
                    if v == ifnames[i]:
                        if_indexes.append ([k, v, ifalias[i]])
                        break
            log.debug('Polling for interfaces: %s', ', '.join(ifnames))
            for i in if_indexes:
                CARBON_STRINGS.extend(poll_interface (m, path, i[1], i[0], i[2], metrics))
    return CARBON_STRINGS


def normalize_ifname(ifname):
    '''Normalizes interfaces for two letter abbreviation and number appended.
       Added exception. If ifname is 3 char long, allow it
    :param ifname: interface name
    :param type: str
    '''
    m = re.match(r'(?P<name>.*?) *(?P<numbers>[0-9-:./]*$)', ifname)
    numbers = m.group('numbers')
    if not numbers:
        name = m.group('name').lower()
    else:
        if len(m.group('name')) > 3:
            name = m.group('name')[0:2].lower()
        else:
            name = m.group('name').lower()
    # Replace dots in ifname by underscores (entreme networks uses dots)
    numbers=numbers.replace ('.','_')
    return '{}{}'.format(name, numbers)


def carbon_all(config):
    '''Creates carbon for each device configured and calls send_carbon()
    :param config: configuration options for devices
    :param type: dict
    '''
    server = (config['carbon']['server'], int(config['carbon']['port']))
    for section in config:
        if section not in ['general', 'carbon', 'logging']:
            for subsection in config[section]:
                sub = config[section][subsection]
                path = sub['metric_path']
                ip = sub['ifaddr']
                snmp_community = sub['snmp_community']
                snmp_version = int(sub['snmp_version'])
                interfaces = sub.get('ifaces', 'all')
                metrics =sub.get ('metrics')
                log.info('Beginning poll of device: %s', ip)
                carbon_data = poll_device(
                    ip, snmp_community,
                    snmp_version, path, metrics, interfaces)
                if carbon_data is False:
                    continue
                log.info('Finished polling device: %s', ip)
                log.debug('Timeseries are: \n%s' % '\n'.join(carbon_data))
                send_carbon(server, carbon_data)
    return True


def send_carbon(server, timeseries):
    '''Open socket and send carbon as packet.
    :param server: server and port to connect to
    :type server: tuple with server as str and port as int
    :param timeseries: list of timeseries to send
    :type timeseries: list of str
    '''
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    log.info('Connecting to %s:%d' % server)
    try:
        sock.connect(server)
    except socket.error:
        log.critical("CRITICAL: Couldn't connect to %s.",  server)

    payload = '\n'.join(timeseries)
    message = payload

    log.info('Beginning data xfer to %s:%d' % server)
    log.debug('-' * 80)
    log.debug(message)
    log.debug('-' * 80)
    try:
        sock.sendall(message)
    except socket.error:
        log.critical("CRITICAL: Couldn't send metrics to %s.",  server)

    log.info('Xfer completed. Closing socket on %s:%d' % server)
    sock.close()


def run(config_dir):
    '''Initiate the process.
    :params: config directory
    '''
    global log
    log = logging.getLogger('snmp-poller')
    log.warning('--- starting ---' + config_dir)
    conf=config.get_config(config_dir)
    interval=conf ['general']['interval']
    while True:
        iTime=time.clock()
        log.info('--- Polling devices ---')
        try:
            carbon_all(conf)
        except:
            log.critical('Unexpected error: %s', sys.exc_info())
        eTime=time.clock()
        sleeping_time=int (interval-(eTime-iTime))
        log.info('--- Finished polling, sleeping for %d seconds ---' % sleeping_time )
        time.sleep(sleeping_time)
