#!/usr/bin/env python
#
# -*- coding: <utf-8> -*-
'''
    communication with the sensors
    main function is    : check_device_dict_via_sensor  - send and receive the device List - reuters a updated version of the list
                        : check_sensor - send a ping to sensor

'''

import socket
from core.Logger import log
from time import sleep
version = "1.2.2"


def writeline_dict(mysock, my_dict):
    mybuffer = ""
    for k, v in my_dict.items():
        mybuffer = mybuffer + k + "\n"    # a3:d2:b8:89:43:ac\n03:d2:b8:89:df:23\n

    mysock.sendall(mybuffer)


def read_tcp(mysock, recv_buffer=1024):
    #
    socket_buffer = mysock.recv(recv_buffer)
    return socket_buffer


def check_sensor(sensor_ip, sensor_port):
    # send a ping to the sensor
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    sensor_address = (sensor_ip, int(sensor_port))

    try:
        sock.connect(sensor_address)
        sock.sendall("ping")
        if sock.recv(5) == "True":
            return True
    except (socket.timeout, socket.error):
        return False
    finally:
        sock.close()


def display_rgbled(sensor_ip, sensor_port, rgb_code):
    ''' Sub Function
        To Display given Text on the Sensor's display

    '''
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)      # timeout should be 5
    sensor_address = (sensor_ip, int(sensor_port))
    try:

        sock.connect(sensor_address)
        sensor_command = "rgbled"
        sock.sendall(sensor_command)
        sleep(0.5)
        sensor_response = sock.recv(5)
        if sensor_response == "True":
            # Sensor accepted the command
            #writeline_dict(sock, disp_text)
            sock.sendall(rgb_code)
            sleep(0.5)
            sensor_response = sock.recv(5)
            if sensor_response == "True":
                # OK
                log("Sensor " + str(sensor_ip) +
                    " showing RGB : " + str(rgb_code), "debug")
            else:
                # ERR
                log("Sensor " + str(sensor_ip) +
                    " has not show RGB LED: " + rgb_code , "debug")
        else:
            log("Sensor " + str(sensor_ip) +
                " did not understand the command " + sensor_command, "debug")

    except (socket.timeout, socket.error):
        log("Sensor " + str(sensor_ip) +
            " timeout - sensor_com.py - display_rgbled", "error")
    finally:
        sock.close()


def display_msg(sensor_ip, sensor_port, disp_text):
    ''' Sub Function
        To Display given Text on the Sensor's display

    '''
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(4)
    sensor_address = (sensor_ip, int(sensor_port))
    try:

        sock.connect(sensor_address)
        sensor_command = "displaytext"
        sock.sendall(sensor_command)
        sleep(0.5)
        sensor_response = sock.recv(5)
        if sensor_response == "True":
            # Sensor accepted the command
            #writeline_dict(sock, disp_text)
            sock.sendall(disp_text)
            sleep(0.5)
            sensor_response = sock.recv(5)
            if sensor_response == "True":
                # OK
                log("Sensor " + str(sensor_ip) +
                    " has displayed Text: " + disp_text , "debug")
            else:
                # ERR
                log("Sensor " + str(sensor_ip) +
                    " has not displayed Text: " + disp_text , "debug")
        else:
            log("Sensor " + str(sensor_ip) +
                " did not understand the command " + sensor_command, "debug")

    except (socket.timeout, socket.error):
        log("Sensor " + str(sensor_ip) +
            " timeout - sensor_com.py - display_msg", "error")
    finally:
        sock.close()


def update_dict_with_response(var_dict, var_response, sensor_ip="unknown"):
    ''' Sub function
         var_dict -
         var_response - string : a3:d2:b8:89:43:ac|True\n03:d2:b8:89:df:23|False\n
    '''
    key_val_to_update = "presence"          # with key value should be updated
    response_dataset_seperator = "\n"       # a set is : a3:d2:b8:89:43:ac|True
    response_val_seperator = "|"

    dict_response = {}

    for item in var_response.split(response_dataset_seperator):
        if len(item) > 21:  # on data set has always 22 characters
            (ks, vs) = item.split(response_val_seperator)
            dict_response[str(ks)] = str(vs)

    if len(dict_response) > 0:
        ''' Updating the given dict with the data's from the sensor. '''
        for k, v in dict_response.items():
            var_dict[k][key_val_to_update] = str(v)
    else:
        log("Sensor " + str(sensor_ip) +
            " responded with an empty device list - sensor_com.py - update_dict_with_response", "error")
    return var_dict


def check_device_dict_via_sensor(sensor_ip, sensor_port, device_dict):
    ''' Main Function!
        Communicating with the sensor, trying to update (update_dict_with_response) the given device's list. In case of
        problems the device list will be returned anyways.
    '''
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    timeout_calc = len(device_dict) * 10                                # we add 10 Sec for each device
    sock.settimeout(timeout_calc)
    sensor_address = (sensor_ip, int(sensor_port))

    try:
        device_dict_processed = {}
        sock.connect(sensor_address)
        sensor_command = "checkdevice"
        sock.sendall(sensor_command)
        sensor_response = sock.recv(5)
        if sensor_response == "True":
            # Sensor accepted the command
            writeline_dict(sock, device_dict)
            sensor_response = sock.recv(5)
            if sensor_response == "True":
                # Sensor accepted the device list
                sensor_response = sock.recv(1024)
                device_dict_processed = dict(update_dict_with_response(device_dict, sensor_response, sensor_ip))
            else:
                # ERROR Sensor cant process the device list
                log("Sensor " + str(sensor_ip) +
                    " cant process the device list - sensor_com.py - check_device_dict_via_sensor", "error")
                device_dict_processed = {}
                print("ERROR - cant process the device list - sensor_com.py")
        else:
            # ERROR Sensor cant process the command
            log("Sensor " + str(sensor_ip) +
                " cant process the command - sensor_com.py - check_device_dict_via_sensor", "error")
            #device_dict_processed = dict(device_dict)
            device_dict_processed = {}
            print("ERROR - cant process the device list - sensor_com.py")
        # Device list will be passed back in any case
        return device_dict_processed

    except (socket.timeout, socket.error):
        log("Sensor " + str(sensor_ip) +
            " timeout - sensor_com.py - check_device_dict_via_sensor", "error")
        return device_dict_processed

    finally:
        sock.close()


def get_sensor_name(sensor_ip, sensor_port):
    ''' Sub Function
        To get the Hostname of the Sensor
    '''

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(6)
    sensor_address = (sensor_ip, int(sensor_port))

    try:

        sock.connect(sensor_address)
        sensor_command = "gethostname"
        sock.sendall(sensor_command)
        sleep(0.5)
        sensor_response = sock.recv(16)

        if sensor_response != "Fals":
            # Sensor accepted the command
            log("Sensor " + str(sensor_ip) +
                " replied with " + sensor_response + " to " + sensor_command, "debug")
            return sensor_response

        else:
            log("Sensor " + str(sensor_ip) +
                " did not understand the command " + sensor_command + ". Sensor need an Update!", "debug")
            return "unknown"

    except (socket.timeout, socket.error):
        log("Sensor " + str(sensor_ip) +
            " timeout - sensor_com.py - get_sensor_name", "error")
        return "unknown"

    finally:
        sock.close()