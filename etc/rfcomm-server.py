#!/usr/bin/python3
from audioop import add
from ftplib import error_perm
from re import sub
from socketserver import ThreadingUnixStreamServer
from bluedot.btcomm import BluetoothServer
from signal import pause
from os.path import exists
from pathlib import Path
import subprocess
import time
import rfcommServerConstants as commands

##########################################################################################
#commands to be executed by controller
##########################################################################################

#verify device

def verify_device(commandnmbr, arg):
	global trust_device
	trusted_devices = open("/etc/bluetooth/trusted_devices.txt", "r")
	passkey = trusted_devices.readline()
	trusted_devices.close()
	if (passkey[:-1] == arg):
		trust_device = 1
		add_trusted_device = open("/etc/bluetooth/trusted_devices.txt", "a")
		add_trusted_device.write(s.client_address + "\n")
		add_trusted_device.close()
		request_verification(chr(0))
	else:
		request_verification(chr(2))
		




##########################################################################################

#update controller

def update_controller(commandnmbr, arg):
	s.send(chr(commandnmbr) + "updating...")
	#git clone etc
	time.sleep(0.5)    #sleep is apparently important, it does something very weird if there is no time inbetween s.send()s
	s.send(chr(commandnmbr) + "updated! rebooting now")

#TODO but not in scope: update controller over bluetooth without the controller being connected to the internet

###########################################################################################

#get controller version

def get_controller_version(commandnmbr):
	s.send(chr(commandnmbr) + "hw=" + open("/sys/firmware/devicetree/base/hardware", "r").read() + "\nsw=" + open("version.txt", "r").read(6))

#TODO triggers update button on the app in the future?

###########################################################################################

#get WiFi networks
#picks up available networks and sends them and the connection status to the app


def get_wifi_networks(commandnmbr):
	#get the list of networks available to the controller
	wifi_list = subprocess.run(["nmcli", "-t", "dev", "wifi"], stdout=subprocess.PIPE, text=True) #(gets the list in a layout optimal for scripting, networks seperated by \n, columns seperated by :)
	#split up the data and filter the important information
	networks = wifi_list.stdout[:-1].split("\n") #split the list at \n characters
	i=len(networks)-1 #set up a variable to loop through the list from the back
	for n in range(len(networks)):
		networks[i] = networks[i].split(":") #split every network up into its components at the : characters
		#print(networks[i])
		if len(networks[i]) < 2:
			networks.pop(i)
		elif networks[i][1]=="": #if this is true the current index contains a network with no name
			networks.pop(i) #remove the networks without a name
		else:
			networks[i].pop(6) #remove the columns of information that dont matter
			networks[i].pop(4)
			networks[i].pop(3)
			networks[i].pop(2)
			#print(ord(networks[i][0]))
			networks[i] = ":".join(networks[i]) #recombine data to send
		i -=1				#iterate 
	
	networks = "\n".join(networks) #recombine data to send
	#print(networks)
	#send data
	s.send(chr(commandnmbr) + networks)
	return

##########################################################################################

#connect to wifi
#runs get_wifi_networks after to update app

def connect_to_wifi(commandnmbr, arg):
	#seperate arg
	message_list = arg.split(":")
	result = subprocess.run(["nmcli", "device", "wifi", "connect", message_list[0], "password", message_list[1]], stdout=subprocess.PIPE, text=True)
	resultstring = result.stdout
	#Error: No network with SSID 'dfg' found.
	#Error: Connection activation failed: (7) Secrets were required, but not provided.
	#Device 'wlan0' successfully activated with 'uuid'
	if (resultstring.find("successfully")!=-1):
		connection_result = 2
	elif (resultstring.find("Secrets")!=-1):
		connection_result = 1
	elif (resultstring.find("SSID")!=-1):
		connection_result = 0
	else:
		connection_result = 3
	s.send(chr(commandnmbr) + chr(connection_result))
	get_wifi_networks(3)

##########################################################################################

#disconnect from wifi network
#runs get_wifi_networks after to update the app

def disconnect_from_wifi(commandnmbr, arg):
	result = subprocess.run(["nmcli", "connection", "delete", "id", arg], stdout=subprocess.PIPE, text=True)
	resultstring = result.stdout
	#Connection 'name' (uuid) succesfully deleted.
	#Error: unknown connection 'name'.\n
	#Error: cannot delete unknown connection(s): id 'name'
	if (resultstring.find("successfully")!=-1):
		disconnection_result = 1
	else:
		disconnection_result = 0
	s.send(chr(commandnmbr) + chr(disconnection_result))
	get_wifi_networks(3)

##########################################################################################
#command_list
##########################################################################################

def command_list(byte, string):
	if byte == commands.VERIFY_DEVICE:
		verify_device(byte, string)
		return
	elif byte == commands.UPDATE_CONTROLLER:
		update_controller(byte, string)
		return
	elif byte == commands.GET_CONTROLLER_VERSION:
		get_controller_version(byte)
		return
	elif byte == commands.GET_WIFI_NETWORKS:
		get_wifi_networks(byte)
		return
	elif byte == commands.CONNECT_TO_WIFI:
		connect_to_wifi(byte, string)
		return
	elif byte == commands.DISCONNECT_FROM_WIFI:
		disconnect_from_wifi(byte, string)
		return

#undsoweiter


##########################################################################################
#bluetooth rfcomm server setup
##########################################################################################

def request_verification(char):
	s.send(chr(commands.VERIFY_DEVICE)+char)

def data_received(data):
	global trust_device
	first_byte = ord(data[0])
	data = data.replace(data[0], '',1)
	if (trust_device == 1 or first_byte == 0):
		command_list(first_byte, data)
	else:
		request_verification(chr(1))

def when_client_connects():
	global trust_device
	trust_device = 0
	connected_client = s.client_address
	trusted_devices = open("/etc/bluetooth/trusted_devices.txt", "r")
	if (trusted_devices.read().find(connected_client) != -1):
		trust_device = 1
		trusted_devices.close()
		get_controller_version(2)
		get_wifi_networks(3)
		return
	trusted_devices.close()
	request_verification(chr(1))

def when_client_disconnects():
	print("connection lost")

s = BluetoothServer(data_received, True, "hci0", 1, "utf-8", False, when_client_connects, when_client_disconnects)
pause()