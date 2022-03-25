#!/usr/bin/python3
from audioop import add
from ftplib import error_perm
from socketserver import ThreadingUnixStreamServer
from bluedot.btcomm import BluetoothServer
import requests
from signal import pause
from os.path import exists
from pathlib import Path
import subprocess
import time
import rfcommServerConstants as commands
import hashlib
from smbus2 import SMBus
from github import Github
# from github import Github

def md5(fname):
	hash_md5 = hashlib.md5()
	with open(fname, "rb") as f:
		for chunk in iter(lambda: f.read(4096), b""):
			hash_md5.update(chunk)
	return hash_md5.hexdigest()

##########################################################################################
#commands to be executed by controller
##########################################################################################

#verify device

def verify_device(commandnmbr, arg):
	#declare global trust variable
	global trust_device
	#get the passkey from the file with trusted_devices
	with open("/etc/bluetooth/trusted_devices.txt", "r") as trusted_devices:
		passkey = trusted_devices.readline()
	#check if the entered passkey is right
	if (passkey[:-1] == arg):
		trust_device = True
		#add device to the trusted list so it doesnt require verification next time
		with open("/etc/bluetooth/trusted_devices.txt", "a") as add_trusted_device:
			add_trusted_device.write(s.client_address + "\n")
		#tell the app that the verification was succesfull
		request_verification(commands.DEVICE_VERIFICATION_SUCCES)
		#sleep for a bit because something goes wrong with the bluetooth messages if you dont
		time.sleep(0.5)
		#send controller version to the app because it hasnt done this upon connection due to not being verified
		get_controller_version(commands.GET_CONTROLLER_VERSION)
	else:
		#inform the app that the entered passkey was not correct
		request_verification(commands.DEVICE_VERIFICATION_INCORRECT_PASSKEY)

#part of the verification structure but is called from multiple places
def request_verification(char):
	send(chr(commands.VERIFY_DEVICE)+chr(char))

##########################################################################################

#update controller

def update_controller(commandnmbr, arg):
	if (arg != ""):
		level1 = ord(arg[0])
		if (level1==commands.UPDATE_FILE_TRANSFER_CHECK):
			level2 = ord(arg[1])
			if (level2 == commands.UPDATE_FILE_APROVED):
				print("file was aproved")
				send(chr(commandnmbr) + chr(commands.UPDATE_STORED_SHA))
			else:
				print("file was corrupted")
		elif (level1==commands.UPDATE_STORED_SHA):
			sha = arg[1:]
			# with open("/etc/module-firmware-update/lastupdatecheck.txt", "w") as file:
			# 	file.write(sha)

###########################################################################################

#get controller version

def get_controller_version(commandnmbr, arg):
	global file_urls
	file_urls = []
	level1 = ord(arg[0])
	
	if (level1 == commands.GET_SHA):
		#set the timeout time for the connection check
		timeout =1
		#attempt to read the head of github.com to see if there is a connection available
		try:
			requests.head("https://www.github.com/", timeout=timeout)
			#tell the app the controller has internet so it can download the update itself
			with open("/etc/module-firmware-update/lastupdatecheck.txt", "r") as file:
				sha = file.read()
			with open("/etc/accesstoken.txt", "r") as file:
				token = file.read()
			g = Github(token)
			r = g.get_repo("Rick-GO/GOcontroll-Moduline")
			cs = r.get_commits(since=r.get_commit(sha).commit.author.date,path="/usr/module-firmware")
			first_run=0
			global last_commit_sha
			for c in cs:
				print("commit found: ")
				print(c.commit.author.date)
				if first_run==0:
					last_commit_sha = c.sha
					first_run += 1
				if sha == c.sha:
					break
				for file in c.files:
					if "srec" in file.filename:
						file_urls.append(file.raw_url)
			if len(file_urls) > 0:
				print(file_urls)
				send(chr(commandnmbr) + chr(commands.CONTROLLER_INTERNET_ACCESS_TRUE) + chr(commands.CONTROLLER_UPDATE_AVAILABLE))
			else:
				send(chr(commandnmbr) + chr(commands.CONTROLLER_INTERNET_ACCESS_TRUE))

			#TODO get the files from github to update

		except requests.ConnectionError:
			#tell the app the controller is not connected to the internet and requires an update over bluetooth
			#TODO add the latest update check date or sha
			with open("/etc/module-firmware-update/lastupdatecheck.txt", "r") as file:
				sha = file.read()
			send(chr(commandnmbr) + chr(commands.CONTROLLER_INTERNET_ACCESS_FALSE) + sha)
	elif (level1 == commands.GET_SETTINGS_INFORMATION):
		#open up the files that contain the versions
		with open("/sys/firmware/devicetree/base/hardware", "r") as file:
			hardware_version = file.read()
		with open("version.txt", "r") as file:
			software_version = file.read(6)
		with open("/etc/machine-info", "r") as file:
			controller_name = file.read().split("=")
		#return the versions to the app
		send(chr(commandnmbr) + chr(commands.GET_SETTINGS_INFORMATION) + hardware_version + ":" + software_version + ":" + controller_name[1])

###########################################################################################

#set transfer mode
#switches between command mode and zip transfer mode.

def set_transfer_mode(commandnmbr, arg):
	#intitialize global variables used for data transfer that only need to be set at the start
	global transfer_mode
	global first_write
	global file_size
	global i
	global progress
	progress = 0
	i = 0
	first_write = 1
	transfer_mode = 1
	#get the file size so the server knows when the full file has been received
	file_size = int(arg)
	#tell the app its cleared to send a file
	send(chr(commandnmbr)+chr(commands.FILE_TRANSFER_ENABLED))

def receive_zip(data):
	#initialize global variables used for data transfer
	global transfer_mode
	global first_write
	global i
	global progress
	global file_size
	#update progress
	progress_check = progress
	#iterate
	i += 1
	#calculate progress
	progress = int(((i*990)/file_size)*100)
	if progress > progress_check: #only send progress when it changes to clear up bluetooth bandwidth
		send(chr(commands.SET_TRANSFER_MODE) + chr(commands.FILE_TRANSFER_PROGRESS) + chr(progress))
	#for the first packet of information the file needs to be created instead of appended
	if first_write == 1:
		with open("/tmp/temporary." + "zip", "wb") as file:
			file.write(data)
		first_write =0
		print("receiving file")
	else:
		with open("/tmp/temporary." + "zip", "ab") as file:
			file.write(data)
	#when te last packet is received
	if file_size/i <= 990:
		#set the transfer mode back to command
		transfer_mode = "command"
		#inform the app that the file has been transferred and that commands are open again
		checksum = md5("/tmp/temporary.zip")
		send(chr(commands.SET_TRANSFER_MODE)+chr(commands.FILE_TRANSFER_COMPLETE)+checksum)
		
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
	#attempt to connect to a network with the given arguments
	result = subprocess.run(["nmcli", "device", "wifi", "connect", message_list[0], "password", message_list[1]], stdout=subprocess.PIPE, text=True)
	#save the result
	resultstring = result.stdout
	#possible results:
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
	#give feedback to the app
	send(chr(commandnmbr) + chr(connection_result))
	#update wifi list to change the state of the network
	get_wifi_networks(commands.GET_WIFI_NETWORKS)

#send(connecttowifi + result int)
##########################################################################################

#disconnect from wifi network
#runs get_wifi_networks after to update the app

def disconnect_from_wifi(commandnmbr, arg):
	#attempt to disconnect from specified network
	result = subprocess.run(["nmcli", "connection", "delete", "id", arg], stdout=subprocess.PIPE, text=True)
	#save the result
	resultstring = result.stdout
	#possible results:
	#Connection 'name' (uuid) succesfully deleted.
	#Error: unknown connection 'name'.\n
	#Error: cannot delete unknown connection(s): id 'name'
	if (resultstring.find("successfully")!=-1):
		disconnection_result = commands.WIFI_DISCONNECT_SUCCES
	else:
		disconnection_result = commands.WIFI_DISCONNECT_FAILED
	#give feedback to the app
	send(chr(commandnmbr) + chr(disconnection_result))
	#update wifi list to change the state of the network
	get_wifi_networks(commands.GET_WIFI_NETWORKS)

#send(disconnectfromwifi + result int)
##########################################################################################

#update the general controller settings

def update_controller_settings(commandnmbr, arg):
	if "GOcontroll" in arg:
		write_device_name(arg)
	else:
		arg = "GOcontroll-" + arg
		write_device_name(arg)

	print(arg)

def write_device_name(name):
	with open("/etc/machine-info", "w") as file:
		file.write("PRETTY_HOSTNAME="+name)

##########################################################################################

#reboot the controller

def reboot_controller():
	subprocess.run(["reboot"])

##########################################################################################
#command_list
##########################################################################################

def command_list(byte, string):
	#turn the incoming bytes into a string
	string = string.decode("utf-8")
	#check which command needs to be executed
	if byte == commands.VERIFY_DEVICE:
		verify_device(byte, string)
		return
	elif byte == commands.UPDATE_CONTROLLER:
		update_controller(byte, string)
		return
	elif byte == commands.GET_CONTROLLER_VERSION:
		get_controller_version(byte, string)
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
	elif byte == commands.UPDATE_CONTROLLER_SETTINGS:
		update_controller_settings(byte,string)
		return
	elif byte == commands.REBOOT_CONTROLLER:
		reboot_controller()
		return
	else:
		send(chr(commands.UNKNOWN_COMMAND) + "unknown command")

#undsoweiter


##########################################################################################
#bluetooth rfcomm server setup
##########################################################################################

#slightly expanded s.send function so not every command has to convert the string to bytes
def send(string):
	s.send(bytes(string, 'utf-8'))

#function that gets called when the controller receives a message
def data_received(data):
	#declare global variables
	global trust_device
	global transfer_mode
	#get the command byte
	first_byte = data[0]
	
	#if the device is trusted or the received command is part of the verification routine
	if (trust_device or first_byte == 0):
		#if the server is set to receive commands or transfer a file
		if transfer_mode == "command":
			print(data)
			#extract the argument from the message
			data = data[1:]
			#run through the commands list
			command_list(first_byte, data)
		else:
			#process raw data for fiel
			receive_zip(data)
	else:
		request_verification(commands.DEVICE_VERIFICATION_MISSING)

#function that gets called when a device connects to the server
def when_client_connects():
	with SMBus(2) as bus:
		bus.write_i2c_block_data(address,23,[255])
		bus.write_i2c_block_data(address,0,[64])
		bus.write_i2c_block_data(address,0x0D,[127])
	#set device to not be trusted and transfer mode to command mode everytime
	global trust_device
	global transfer_mode
	transfer_mode = "command"
	trust_device = False
	#log the connection in the terminal and save the mac address in a variable
	connected_client = s.client_address
	print("connected to: " + connected_client)
	#check if the connected device is trusted
	with open("/etc/bluetooth/trusted_devices.txt", "r") as trusted_devices:
		if (trusted_devices.read().find(connected_client) != -1):
			trust_device = True
			get_controller_version(commands.GET_CONTROLLER_VERSION, chr(commands.GET_SHA))
			return
		#if not request verification
		else:
			request_verification(commands.DEVICE_VERIFICATION_MISSING)

#function that gets called when a device disconnects from the server
def when_client_disconnects():
	with SMBus(2) as bus:
		bus.write_i2c_block_data(address,0x0D,[0])
	print("connection lost")

#defines a variable which can be interacted with for bluetooth functions
#sets up callback functions and how the received/sent data is processed
s = BluetoothServer(data_received, True, "hci0", 1, None, False, when_client_connects, when_client_disconnects)
global address
address = 20
pause()
