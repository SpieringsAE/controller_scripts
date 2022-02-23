#!/usr/bin/python3
from ftplib import error_perm
from re import sub
from bluedot.btcomm import BluetoothServer
from signal import pause
import subprocess
import time

##########################################################################################
#commands to be executed by controller
##########################################################################################

#update controller

def update_controller(commandnmbr, arg):
	print(arg)
	s.send(chr(commandnmbr) + "updating...")
	#git clone etc
	time.sleep(0.5)    #sleep is apparently important, it does something very weird if there is no time inbetween s.send()s
	s.send(chr(commandnmbr) + "updated! rebooting now")

#TODO but not in scope: update controller over bluetooth without the controller being connected to the internet

###########################################################################################

#get the version of the controller (potentially match this with updates to the app to determine whether the controller could be updated)
#runs when phone and controller are connected

def get_controller_version(commandnmbr, arg):
	print(arg)
	s.send(chr(commandnmbr) + "hw" + open("/sys/firmware/devicetree/base/hardware", "r").read() + "sw") #add software version

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
	get_wifi_networks(2)

##########################################################################################

#disconnect from wifi network
#runs get_wifi_networks after to update the app

def disconnect_from_wifi(commandnmbr, arg):
	result = subprocess.run(["nmcli", "connection", "delete", "id", arg], stdout=subprocess.PIPE, text=True)
	resultstring = result.stdout
	#Connection 'name' (uuid) succesfully deleted.
	#Error: unknown connection 'name'.\n
	#Eroor: cannot delete unknown connection(s): id 'name'
	if (resultstring.find("successfully")!=-1):
		disconnection_result = 1
	else:
		disconnection_result = 0
	s.send(chr(commandnmbr) + chr(disconnection_result))
	get_wifi_networks(2)

##########################################################################################
#command_list

def command_list(byte, string):
	if byte == 0:
		update_controller(byte, string)
		return
	elif byte == 1:
		get_controller_version(byte, string)
		return
	elif byte == 2:
		get_wifi_networks(byte)
		return
	elif byte == 3:
		connect_to_wifi(byte, string)
		return
	elif byte == 4:
		disconnect_from_wifi(byte, string)
		return

#undsoweiter


##########################################################################################
#bluetooth rfcomm server setup

def data_received(data):
	eerste_byte = ord(data[0])
	data = data.replace(data[0], '',1)
	command_list(eerste_byte, data)

s = BluetoothServer(data_received)
pause()
