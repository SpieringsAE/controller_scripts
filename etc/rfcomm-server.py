#!/usr/bin/python3
from audioop import add
from ftplib import error_perm
from re import I, sub
from socketserver import ThreadingUnixStreamServer
from wsgiref.simple_server import software_version
from bluedot.btcomm import BluetoothServer
import requests
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
		request_verification(chr(commands.DEVICE_VERIFICATION_SUCCES))
		time.sleep(0.5)
		get_controller_version
	else:
		request_verification(chr(commands.DEVICE_VERIFICATION_INCORRECT_PASSKEY))

##########################################################################################

#update controller

def update_controller(commandnmbr, arg):
	timeout =1
	try:
		requests.head("https://www.github.com/", timeout=timeout)
		send(chr(commandnmbr) + chr(commands.CONTROLLER_INTERNET_ACCESS_TRUE))

	except requests.ConnectionError:
		send(chr(commandnmbr) + chr(commands.CONTROLLER_INTERNET_ACCESS_FALSE))
	# if arg == 0:
	# 	#files have been sent by the phone so are already available on the controller
	# 	subprocess.run(["unzip", "/tmp/temporary.zip"])
	# 	subprocess.run(["rm", "/tmp/temporary.zip"])
	# 	#subprocess.run([""])
	# else:
	# 	print("get files from git")
	# #git clone etc
	# time.sleep(0.5)    #sleep is apparently important, it does something very weird if there is no time inbetween s.send()s
	# send(chr(commandnmbr) + "updated! rebooting now")

#TODO but not in scope: update controller over bluetooth without the controller being connected to the internet

###########################################################################################

#get controller version

def get_controller_version(commandnmbr):
	hardware_version = open("/sys/firmware/devicetree/base/hardware", "r").read()
	software_version = open("version.txt", "r").read(6)
	print("Hardware version: "+ hardware_version)
	print("Software version: "+ software_version)
	send(chr(commandnmbr) + hardware_version + "\n" + software_version)

#TODO triggers update button on the app in the future?

###########################################################################################

#set transfer mode
#switches between command mode and zip transfer mode.

def set_transfer_mode(commandnmbr, arg):
	global transfer_mode
	global first_write
	global file_size
	global i
	global progress
	progress = 0
	i = 0
	first_write = 1
	transfer_mode = 1
	file_size = int(arg)

	print("setting transfer mode")
	send(chr(commandnmbr)+chr(commands.FILE_TRANSFER_ENABLED))

def receive_zip(data):
	global transfer_mode
	global first_write
	global i
	global progress
	progress_check = progress
	i += 1
	progress = int(((i*990)/file_size)*100)
	if progress > progress_check: #only send progress when it changes to clear up bluetooth bandwidth
		send(chr(commands.SET_TRANSFER_MODE) + chr(commands.FILE_TRANSFER_PROGRESS) + str(progress))
		#print(progress)
	if first_write == 1:
		file_type = data[1:4].decode("utf-8")
		with open("/tmp/temporary." + file_type, "wb") as file:
			file.write(data)
		first_write =0
		print("receiving file")
	else:
		with open("/tmp/temporary."+ file_type, "ab") as file:
			file.write(data)
	if file_size/i <= 990:
		transfer_mode = "command"
		send(chr(commands.SET_TRANSFER_MODE)+chr(commands.FILE_TRANSFER_COMPLETE))
		print("commands enabled")

#send(filetransfer + filetransfer state + (progress))
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
			if networks[i][3] == "":
				networks[i][3] = "No Security"
			networks[i] = ":".join(networks[i]) #recombine data to send
		i -=1				#iterate 
	
	networks = "\n".join(networks) #recombine data to send
	#print(networks)
	#send data
	send(chr(commandnmbr) + networks)
	return

#send(getwifinetworks + net list)
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
		connection_result = commands.WIFI_CONNECT_SUCCES
	elif (resultstring.find("Secrets")!=-1):
		connection_result = commands.WIFI_CONNECT_FAILED_INC_PW
	elif (resultstring.find("SSID")!=-1):
		connection_result = commands.WIFI_CONNECT_FAILED_INC_SSID
	else:
		connection_result = commands.WIFI_CONNECT_FAILED_UNKNOWN
	send(chr(commandnmbr) + chr(connection_result))
	get_wifi_networks(commands.GET_WIFI_NETWORKS)

#send(connecttowifi + result int)
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
		disconnection_result = commands.WIFI_DISCONNECT_SUCCES
	else:
		disconnection_result = commands.WIFI_DISCONNECT_FAILED
	send(chr(commandnmbr) + chr(disconnection_result))
	get_wifi_networks(commands.GET_WIFI_NETWORKS)

#send(disconnectfromwifi + result int)
##########################################################################################
#command_list
##########################################################################################

def command_list(byte, string):
	string = string.decode("utf-8")
	if byte == commands.VERIFY_DEVICE:
		verify_device(byte, string)
		return
	elif byte == commands.UPDATE_CONTROLLER:
		update_controller(byte, string)
		return
	elif byte == commands.GET_CONTROLLER_VERSION:
		get_controller_version(byte)
		return
	elif byte == commands.SET_TRANSFER_MODE:
		set_transfer_mode(byte, string)
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
	else:
		send(chr(commands.UNKNOWN_COMMAND) + "unknown command")

#undsoweiter


##########################################################################################
#bluetooth rfcomm server setup
##########################################################################################

def request_verification(char):
	send(chr(commands.VERIFY_DEVICE)+char)

def send(string):
	s.send(bytes(string, 'utf-8'))

def data_received(data):
	#print(data)
	global trust_device
	global transfer_mode
	first_byte = data[0]
	if (trust_device == 1 or first_byte == 0):
		if transfer_mode == "command":
			#data = data.replace(data[0], '',1)
			data = data[1:]
			command_list(first_byte, data)
		else:
			receive_zip(data)
	else:
		request_verification(chr(1))

def when_client_connects():
	global trust_device
	global transfer_mode
	transfer_mode = "command"
	trust_device = 0
	connected_client = s.client_address
	print("connected to: " + connected_client)
	trusted_devices = open("/etc/bluetooth/trusted_devices.txt", "r")
	if (trusted_devices.read().find(connected_client) != -1):
		trust_device = 1
		trusted_devices.close()
		get_controller_version(2)
		#get_wifi_networks(3)
		return
	trusted_devices.close()
	request_verification(chr(1))

def when_client_disconnects():
	print("connection lost")

s = BluetoothServer(data_received, True, "hci0", 1, None, False, when_client_connects, when_client_disconnects)
pause()