#!/usr/bin/python

import suds.client
import logging
import ConfigParser
import os
import sys
import socket

configfile = '/etc/r1soft.ini'
mysqlconfigfile = '/root/.my.cnf'

if not os.path.exists(configfile):
        print "Il file di configurazione di r1soft non esiste, crealo please..."
        sys.exit()

# Prendo i dati dal file di configurazione:
config = ConfigParser.ConfigParser()
config.read(configfile)

#Popolo le variabili

cdp_host = config.get('r1soft','url')
recovery_point_limit = config.get('r1soft','recovery_point_limit')
volume = config.get('r1soft','volume')
cp_name = config.get('r1soft','cp_name')
tmphours=config.get('r1soft','hours')
#Converto la stringa tmphours in un array numerico da passare alla policy
hours=map(int, tmphours.split(','))

minutes=config.get('r1soft','minutes')

# Eseguo r1soft-setup --get-key con il parametro il nome dell'host specificato nel file /etc/r1soft.ini
comando_r1soft="r1soft-setup --get-key https://"+cdp_host
os.system(comando_r1soft)

username = 'XXXXXXX'
password = "XXXXXXX"

use_db_addon = True
sqluser = 'root'

hostname = socket.gethostname()
description = hostname


# Prendo i dati dal file di configurazione:
config = ConfigParser.ConfigParser()
config.read(mysqlconfigfile)
tempsqlpass = config.get('client','password')
sqlpass = tempsqlpass.replace('"', "")

logger = logging.getLogger('cdp-add-agent')
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)
logger.propagate = False

class MetaClient(object):
    def __init__(self, url_base, **kwargs):
        self.__url_base = url_base
        self.__init_args = kwargs
        self.__clients = dict()

    def __getattr__(self, name):
        c = self.__clients.get(name, None)
        logger.debug('Accessing SOAP client: %s' % name)
        if c is None:
            logger.debug('Client doesn\'t exist, creating: %s' % name)
            c = suds.client.Client(self.__url_base % name, **self.__init_args)
            self.__clients[name] = c
        return c

def get_wsdl_url(hostname, namespace, use_ssl=True, port_override=None):
    if use_ssl:
        proto = 'https'
    else:
        proto = 'http'
    if port_override is None:
        if use_ssl:
            port = 9443
        else:
            port = 9080
    else:
        port = port_override
    url = '%s://%s:%d/%s?wsdl' % (proto, hostname, port, namespace)
    logging.debug('Creating WSDL URL: %s' % url)
    return url

if __name__ == '__main__':
    import sys
    import os

    logger.info('Setting up backups for host (%s) on CDP server (%s) with description: %s', hostname, cdp_host, description)
    client = MetaClient(get_wsdl_url(cdp_host, '%s'), username=username, password=password,faults=True)
    logger.debug('Creating special types...')
    DiskSafeObject = client.DiskSafe.factory.create('diskSafe.disksafe')
    CompressionType = client.DiskSafe.factory.create('diskSafe.compressionType')
    CompressionLevel = client.DiskSafe.factory.create('diskSafe.compressionLevel')
    DeviceBackupType = client.DiskSafe.factory.create('diskSafe.deviceBackupType')
    FrequencyType = client.Policy2.factory.create('frequencyType')
    FrequencyValues = client.Policy2.factory.create('frequencyValues')
    ControlPanelList = client.Policy2.factory.create('policy.controlPanelInstanceList')
    ExcludeList = client.Policy2.factory.create('policy.excludeList')
    ExcludeList2 = client.Policy2.factory.create('policy.excludeList')
    ExcludeList3 = client.Policy2.factory.create('policy.excludeList')
    ExcludeList4 = client.Policy2.factory.create('policy.excludeList')
    ExcludeList5 = client.Policy2.factory.create('policy.excludeList')
    ExcludeList6 = client.Policy2.factory.create('policy.excludeList')
    ExcludeList7 = client.Policy2.factory.create('policy.excludeList')
    ExcludeList8 = client.Policy2.factory.create('policy.excludeList')
    ExcludeList9 = client.Policy2.factory.create('policy.excludeList')
    logger.debug('Created special types')
    logger.debug('Getting volumes...')
    volumes = client.Volume.service.getVolumes()

    # Scelgo il volume su cui backuppare. Esiste solo sda o sdb

    if 'sda' in volume:
	volume=volumes[0]
    else:
	volume=volumes[1]

    logger.info('Using volume %s', volume.name)
    logger.debug('Creating agent for host: %s', hostname)
    agent = client.Agent.service.createAgent(
        hostname=hostname,
        portNumber=1167,
        description=description,
        databaseAddOnEnabled=use_db_addon
    )
    logger.info('Created agent for host (%s) with ID: %s', hostname, agent.id)
    logger.debug('Creating disksafe for agent (%s) on volume (%s)', agent.id, volume.id)
    DiskSafeObject.description = hostname
    DiskSafeObject.agentID = agent.id
    DiskSafeObject.volumeID = volume.id
    DiskSafeObject.compressionType = CompressionType.QUICKLZ
    DiskSafeObject.compressionLevel = CompressionLevel.HIGH
    DiskSafeObject.deviceBackupType = DeviceBackupType.AUTO_ADD_DEVICES
    DiskSafeObject.backupPartitionTable = False
    DiskSafeObject.backupUnmountedDevices = False
    disksafe = client.DiskSafe.service.createDiskSafeWithObject(DiskSafeObject)
    logger.info('Created disksafe with ID: %s', disksafe.id)
    #FrequencyValues.hoursOfDay = [0,4,8,12]
    FrequencyValues.hoursOfDay = hours
    FrequencyValues.startingMinute = minutes
    logger.debug('Creating policy for agent (%s) on disksafe (%s)',
        hostname, disksafe.id)
    policy = client.Policy2.factory.create('policy')
    policy.enabled = True
    policy.name = hostname
    policy.description = description
    policy.diskSafeID = disksafe.id
    policy.mergeScheduleFrequencyType = FrequencyType.ON_DEMAND
    policy.replicationScheduleFrequencyType = FrequencyType.DAILY
    policy.replicationScheduleFrequencyValues = FrequencyValues
    policy.recoveryPointLimit = recovery_point_limit
    policy.forceFullBlockScan = False
    policy.localArchivingEnabled = True
    policy.localRetentionSettings.dailyLimit=7
    policy.localRetentionSettings.weeklyLimit=2
    ExcludeList.exclusionPattern="/home/"
    ExcludeList.isRecursive=False
    policy.excludeList=[ExcludeList]
    
    ControlPanelList.controlPanelType="CPANEL"
    ControlPanelList.enabled="true"
    ControlPanelList.name=cp_name
    policy.controlPanelInstanceList=[ControlPanelList]
 


    if use_db_addon:
        dbi = client.Policy2.factory.create('databaseInstance')
        dbi.dataBaseType = client.Policy2.factory.create('dataBaseType').MYSQL
        dbi.enabled = True
        dbi.hostName = 'localhost'
        dbi.name = 'default'
        dbi.username = sqluser
        dbi.password = sqlpass
        dbi.portNumber = 3306
        dbi.useAlternateDataDirectory = False
        dbi.useAlternateHostname = True
        dbi.useAlternateInstallDirectory = False
        policy.databaseInstanceList = [dbi]

    policy = client.Policy2.service.createPolicy(policy=policy)
    logger.info('Created policy with ID: %s', policy.id)
    logger.info('Finished setting up backups for host: %s', hostname)

