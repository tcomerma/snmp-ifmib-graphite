import time
import socket
import re
from snimpy.snmp import SNMPException
from snimpy.manager import Manager
from snimpy.manager import load
from SNMPPoll import logger, config

log = logger.logger


def poll_device(ip, snmp_community, snmp_version, path, interfaces='all'):
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
    TIMESTAMP = int(time.time())
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
    if interfaces == 'all':
        log.info('Polling for interfaces: %s', interfaces)
        for iface in m.ifIndex:
            if str(m.ifAdminStatus[iface]) == 'up(1)' and \
                    str(m.ifName[iface]) not in NULL_IFS:
                iface_name = normalize_ifname(str(m.ifName[iface]))
                path_out = '%s.%s.tx' % (path, iface_name)
                path_in = '%s.%s.rx' % (path, iface_name)
                octets_out = int(m.ifHCOutOctets[iface])
                octets_in = int(m.ifHCInOctets[iface])
                timeseries_out = '%s %s %s' % (path_out, octets_out, TIMESTAMP)
                timeseries_in = '%s %s %s' % (path_in, octets_in, TIMESTAMP)
                CARBON_STRINGS.extend([timeseries_out, timeseries_in])
    # Need to combine most of this if/els together. Too much being repeated..
    else:
        if isinstance(interfaces, basestring):
            interface_tmp = interfaces
            interfaces = []
            interfaces.append(interface_tmp)
        elif isinstance(interfaces, list):
            log.info('Polling for interfaces: %s', ', '.join(interfaces))
            if_indexes = \
                {v: k for k, v in m.ifName.iteritems() if v in interfaces}
            for iface, index in if_indexes.iteritems():
                iface_name = normalize_ifname(str(iface))
                path_out = '%s.%s.tx' % (path, iface_name)
                path_in = '%s.%s.rx' % (path, iface_name)
                path_ifHighSpeed = '%s.%s.HighSpeed' % (path, iface_name)
                octets_out = int(m.ifHCOutOctets[index])
                octets_in = int(m.ifHCInOctets[index])
                octets_ifHighSpeed = int(m.ifHighSpeed[index])
                timeseries_out = '%s %s %s' % (path_out, octets_out, TIMESTAMP)
                timeseries_in = '%s %s %s' % (path_in, octets_in, TIMESTAMP)
                timeseries_ifHighSpeed = '%s %s %s' % (path_ifHighSpeed, octets_ifHighSpeed, TIMESTAMP)

                CARBON_STRINGS.extend([timeseries_out, timeseries_in, timeseries_ifHighSpeed])
    return CARBON_STRINGS


def normalize_ifname(ifname):
    '''Normalizes interfaces for two letter abbreviation and number appended.
    :param ifname: interface name
    :param type: str
    '''
    m = re.match(r'(?P<name>.*?) *(?P<numbers>[0-9-:./]*$)', ifname)
    numbers = m.group('numbers')
    if not numbers:
        name = m.group('name').lower()
    else:
        name = m.group('name')[0:2].lower()
    return '{}{}'.format(name, numbers)


def carbon_all(config):
    '''Creates carbon for each device configured and calls send_carbon()
    :param config: configuration options for devices
    :param type: dict
    '''
    server = (config['carbon']['server'], int(config['carbon']['port']))
    for section in config:
        if section not in ['carbon', 'logging']:
            for subsection in config[section]:
                sub = config[section][subsection]
                path = sub['metric_path']
                ip = sub['ifaddr']
                snmp_community = sub['snmp_community']
                snmp_version = int(sub['snmp_version'])
                interfaces = sub.get('ifaces', 'all')
                log.info('Beginning poll of device: %s', ip)
                carbon_data = poll_device(
                    ip, snmp_community,
                    snmp_version, path, interfaces)
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
    :params: none
    '''
    return carbon_all(config.get_config(config_dir))
