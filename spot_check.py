#!/usr/bin/env python
#
# -*- coding: <utf-8> -*-
"""
The Protocol:
    (Start)
    Expecting first a function that should be processed

    (End)
    After the function is done, the application go back to waiting for command mode
"""
import os
import socket
import time
import datetime
import copy
import core
from optparse import OptionParser
from core.Helper import get_local_ip
from core.Logger import log
from core.daemon import startstop
from core.homematic import get_device_to_check, send_device_status_to_ccu
from core.udpclient import updclientstart
from core.sensor_com import check_device_dict_via_sensor, check_sensor

version = "1.1.9"
core.LOG_FILE_NAME = "spot_check"
print("------------------- spot_check %s -------------------") % version


def writeline(mysock, mymsg):
    mysock.sendall(mymsg)


def getsock():
    # Create a TCP/IP socket
    while (get_local_ip('8.8.8.8') == None):
        time.sleep(1)
    myip = get_local_ip('8.8.8.8')
    log("GetSock got the IP : " + str(myip), "debug")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    log("Bind the socket to the Port : " + str(core.SRV_PORT), "info")
    server_address = ('', core.SRV_PORT)
    try:
        sock.bind(server_address)
        log("starting up socket, port: " + str(core.SRV_PORT), "debug")
    except socket.error:
        log("Port : " + str(core.SRV_PORT) + " is already in use, changing port", "info")
        core.SRV_PORT += 1
        server_address = ('', core.SRV_PORT)
        sock.bind(server_address)
        log("starting up socket, port: " + str(core.SRV_PORT), "info")
    return sock


def read_tcp(mysock, recv_buffer=1024):
    sockbuffer = mysock.recv(recv_buffer)
    return sockbuffer


def readlines(mysock, recv_buffer=4096, delim='\n'):
    """
    :rtype: lese die TCP daten DS mit return getrennt
    """
    tcpbuffer = mysock.recv(recv_buffer)

    while tcpbuffer.find(delim) != -1:
        line, tcpbuffer = tcpbuffer.split('\n', 1)
        yield line
    return


def readlines_to_dict(sock):
    message = {}
    for line in readlines(sock):
        log("Command parameter received : " + str(line), "debug")
        message[line] = ""
    return message


def writelimes(mysock, mymsg):
    mysock.sendall(mymsg)


def cumulate_sensor_data(sensor_data):
    ''' sensor_data
        ["192.168.1.100" = ["CC:29:F5:67:B7:EC" = [ (presence = True) ] ] ]
    '''
    device_dict = {}
    for k, v in sensor_data.items():
        for device_key, device_val in v.items():
            if device_val["presence"] == "True":
                try:
                    device_dict[device_key] += 1
                except KeyError:
                    device_dict[device_key] = 1
            else:
                try:
                    device_dict[device_key] += 0
                except KeyError:
                    device_dict[device_key] = 0
    return device_dict


def discovery_devices(wait_till_found=True):
    # get the devices from the ccu2
    try:
        while get_local_ip("8.8.8.8") is None:      # check if we have a ip
            time.sleep(1)

        devices_to_check = get_device_to_check()
        if wait_till_found:
            while devices_to_check is None:
                time.sleep(2)
                devices_to_check = get_device_to_check()
        return devices_to_check

    except KeyboardInterrupt:
        log("Got signal to STOP", "info")
        if core.PROG_DAEMONIZE:
            startstop(pidfile=core.PDI_FILE, startmsg='stopping daemon', action='stop')
        else:
            print("KeyboardInterrupt received, stopping work ")
        os._exit(0)


def discovery_sensors(wait_till_found=True):
    # get look up for the sensors
    # sensors are storage at core.SPOT_SENSOR
    try:
        while get_local_ip("8.8.8.8") is None:      # check if we have a ip
            time.sleep(1)

        if wait_till_found:
            updclientstart()
            while len(core.SPOT_SENSOR) == 0:
                updclientstart()
                time.sleep(1)
        else:
            updclientstart()
    except KeyboardInterrupt:
        log("Got signal to STOP", "info")
        if core.PROG_DAEMONIZE:
            startstop(pidfile=core.PDI_FILE, startmsg='stopping daemon', action='stop')
        else:
            print("KeyboardInterrupt received, stopping work ")
        os._exit(0)


def main():
    log("Starting to collect parameters", "info")
    log("checking if ip interface is ready", "debug")
    # wait till we have an ip
    while get_local_ip("8.8.8.8") is None:
        time.sleep(1)
    log("IP interface ready to go! local IP : " + str(get_local_ip("8.8.8.8")), "debug")

    if core.AUTO_DISCOVERY:
        log("Running Auto Discovery for Sensors ", "debug")
        discovery_sensors()
    log("Getting Devices for check from CCU2", "debug")
    # we will work with devices_to_check all the time and save the response from the sensors here
    devices_to_check = discovery_devices()

    log("All parameters collected. System OK -> STARTING WORK", "info")

    try:
        request_discovery = False               # sometimes I'll rediscover sensors and the "device to check list"
        counter = 0                             # loop counter
        while True:
            counter += 1                        # count every loop
            sensor_data = {}
            if request_discovery:               # in some cases we will need to rediscover sensors and devices
                request_discovery = False
                log("Rediscovering Sensor and devices. Loop : " + str(counter), "debug")
                devices_to_check = {}
                devices_to_check = copy.deepcopy(discovery_devices())
                discovery_sensors()

            # send the device list to all sensors, store all in sensor_data[k]
            for k, v in core.SPOT_SENSOR.items():
                # (k)ey = IP-Address
                # (v)alue = Port
                if check_sensor(k, v):  # ping the sensor
                    cp_device = {}
                    cp_device = copy.deepcopy(devices_to_check)                     # avoiding references by deepcopy
                    sensor_data[k] = check_device_dict_via_sensor(k, v, cp_device)  # collect dates from all sensors
                else:
                    log("Sensor ping failed to : " + str(k) + " . Moving on to the next sensor", "debug")
                    request_discovery = True
            presence_of_devices = {}
            presence_of_devices = cumulate_sensor_data(sensor_data)

            # create a time stamp
            time_now = time.time()
            time_stamp = datetime.datetime.fromtimestamp(time_now).strftime('%Y-%m-%d-%H:%M:%S')
            if len(presence_of_devices) == 0:
                log("All Sensors down. loop counter " + str(counter), "debug")
                request_discovery = True
            else:
                # checking if device presence has changed
                for k, v in devices_to_check.items():
                    #print (v)
                    if devices_to_check[k]['presence'].lower() == 'true' and presence_of_devices[k] > 0:
                        # was visible   ist visible     do nothing
                        log(str(k) + " is still presence. Loop : " + str(counter), "debug")

                    elif devices_to_check[k]['presence'].lower() == 'true' and presence_of_devices[k] == 0 and \
                        devices_to_check[k]['times_not_seen'] < core.MAX_TIME_NOT_SEEN:
                        # was visible   ist not visible < MAX   count not seen + 1, set first time not seen
                        devices_to_check[k]['times_not_seen'] += 1
                        if devices_to_check[k]['first_not_seen'] is None:
                            devices_to_check[k]['first_not_seen'] = time_stamp

                    elif devices_to_check[k]['presence'].lower() == 'true' and presence_of_devices[k] == 0 and \
                                    devices_to_check[k]['times_not_seen'] >= core.MAX_TIME_NOT_SEEN:
                        # was visible   ist not visible = MAX!   update ccu2, was visible = False
                        # send update to ccu2
                        send_ok = send_device_status_to_ccu(devices_to_check[k]['ise_id'], 'false')
                        log(str(k) + " - " + str(devices_to_check[k]['name']) + \
                            " is not more seen since " + \
                            str(devices_to_check[k]['first_not_seen']) + ". Update sent to CCU2", "info")

                        if send_ok:      # successful
                            log(str(k) + " successful updated change to CCU2", "debug")
                        else:
                            log(str(k) + " problem by updated change to CCU2", "debug")
                        devices_to_check[k]['presence'] = 'False'                       # update the dict
                        # passing to a DB ->
                    elif devices_to_check[k]['presence'].lower() == 'false' and presence_of_devices[k] > 0:
                        # was not visible   ist visible        update ccu2, was visible = True, reset counter and stamp
                        # send update to ccu2
                        send_ok = send_device_status_to_ccu(devices_to_check[k]['ise_id'], 'true')
                        log(str(k) + " - " + str(devices_to_check[k]['name']) + \
                            " is seen now. Update send to CCU2", "info")
                        if send_ok:      # successful
                            log(str(k) + " successful updated change to CCU2", "debug")
                        else:
                            log(str(k) + " problem by updated change to CCU2", "debug")
                        devices_to_check[k]['times_not_seen'] = 0                       # reset not seen counter to 0
                        devices_to_check[k]['first_not_seen'] = None                    # reset first time stamp
                        devices_to_check[k]['presence'] = 'True'                        # update the dict
                        # passing to a DB ->
                    else:
                        log(str(k) + " is still not presence", "debug")

                # if activated, send a alive signal to ccu2. To activate it, u need to create a
                # system variable ('last_update_') on the ccu2
                if core.CCU_LAST_UPDATE is not None:
                    send_ok = send_device_status_to_ccu('last_update_', '"' + time_stamp + '"')

            if counter > 100:           # Rediscover after every x loops
                counter = 0
                request_discovery = True

            time.sleep(core.SLEEP_TIMER)

    except KeyboardInterrupt:
        log("Got signal to STOP", "info")
        if core.PROG_DAEMONIZE:
            startstop(pidfile=core.PDI_FILE, startmsg='stopping daemon', action='stop')
        else:
            print("KeyboardInterrupt received, stopping work ")
        os._exit(0)


if __name__ == "__main__":
    # Set up and gather command line arguments
    usage = "usage: %prog [-options] [arg]"
    p = OptionParser(usage=usage)

    p.add_option('-m', '--manually',
                 dest='manually', help="Automatic Discovery Mode off - manually set up a sensor (ip:port)")
    p.add_option('-d', '--daemonize', action="store_true",
                 dest='daemonize', help="Run the server as a daemon")
    p.add_option('-p', '--pidfile',
                 dest='pidfile', default=None,
                 help="Store the process id in the given file")
    p.add_option('-t', '--test', action="store_true",
                 dest='test', default=None,
                 help="function test")
    p.add_option('-l', '--log', action="store_true",
                 dest='log', help="set log to DEBUG.")
    p.add_option('-s', '--stop', action="store_true",
                 dest='stop', help="stop the daemon")
    p.add_option('-r', '--restart', action="store_true",
                 dest='restart', help="restart the daemon")
    p.add_option('-i', '--status', action="store_true",
                 dest='status',  help="status of the daemon")

    options, args = p.parse_args()

    if options.manually:
        # Set port
        # nametmp = nametmp.split('_')
        #try:
        #core.SPOT_SENSOR = options.manually.split(':')
        core.SPOT_SENSOR = dict(item.split(":") for item in options.manually.split(","))
        #except error:
        print "------------------- IP manual set to " + options.manually + " -------------------"
        if len(core.SPOT_SENSOR) < 1:
            p.error("Sensor IP and Port (10.1.1.2:10002) Mandatory if you not using Automatic Discovery Mode off (-m)")
    else:
        core.AUTO_DISCOVERY = True

    # PIDfile
    if options.pidfile:
        print "------------------- Set PIDfile to " + options.pidfile + " -------------------"
        log("Set PIDfile to " + options.pidfile, "info")
        core.PDI_FILE = str(options.pidfile)

    # Set LOG
    if options.log:
        print "------------------- Log DEBUG manual set to True -------------------"
        core.DEBUG_LOG = True
        log("DEBUG LOG manual set to True ", "debug")
    else:
        core.DEBUG_LOG = None

    # Teste Funktion!
    if options.test:
        print "------------------- Test of a function -------------------"
        core.DEBUG_LOG = True
        log("Test of a function, auto debug True ", "debug")
        p.error("Function test End")

    if options.stop:
        log("Got the option to stop the Daemon ", "debug")
        startstop(pidfile=core.PDI_FILE, startmsg='stopping daemon', action='stop')
    elif options.restart:
        log("Got the option to restart the Daemon ", "debug")
        startstop(pidfile=core.PDI_FILE, startmsg='restarting daemon', action='restart')
    elif options.status:
        log("Got the option to return the Daemon status", "debug")
        startstop(stdout='.', stderr=None, stdin='.',
                  pidfile=core.PDI_FILE, startmsg='status of daemon', action='status')
    elif options.daemonize:
        print "------------------- Preparing to run in daemon mode -------------------"
        log("Preparing to run in daemon mode", "info")
        startstop(pidfile=core.PDI_FILE, action='start')
    else:
        print("Terminal Mode")

    main()