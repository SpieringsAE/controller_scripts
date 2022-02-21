#!/usr/bin/python3
from ftplib import error_perm
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
#TODO write function to get available WiFi networks
#def get_wifi_networks()
#picks up available networks and sends them and the connection status to the app


def get_wifi_networks(commandnmbr, arg):
	#get the list of networks available to the controller
	wifi_list = subprocess.run(["nmcli", "-t", "dev", "wifi"], stdout=subprocess.PIPE, text=True) #(gets the list in a layout optimal for scripting, networks seperated by \n, columns seperated by :)
	#split up the data and filter the important information
	networks = wifi_list.stdout[:-1].split("\n") #split the list at \n characters
	i=len(networks)-1 #set up a variable to loop through the list from the back
	for n in range(len(networks)):
		networks[i] = networks[i].split(":") #split every network up into its components at the : characters
		if networks[i][1]=="": #if this is true the current index contains a network with no name
			networks.pop(i) #remove the networks without a name
		else:
			networks[i].pop(6) #remove the columns of information that dont matter
			networks[i].pop(4)
			networks[i].pop(3)
			networks[i].pop(2)
			print(ord(networks[i][0]))
			networks[i] = ":".join(networks[i]) #recombine data to send
		i -=1				#iterate 
	
	networks = "\n".join(networks) #recombine data to send
	print(networks)
	#send data
	s.send(chr(commandnmbr) + networks)
	return

##########################################################################################

#connect to wifi
#TODO write function to connect to a network
#def connect_to_wifi(name, psk, security)
#write wpa_supplicant.conf file
#run wpa_supplicant to connect
#runs get_wifi_networks after to update app

def connect_to_wifi(commandnmbr, arg):
	#arg uit elkaar halen
	#name =
	#psk =
	#security = 
	#checken of het gelukt is
	#if (niet gelukt)
		#s.send(reden waarom het niet gelukt is, verkeerd wachtwoord bijvoorbeeld)
	#else
		#get_wifi_networks(commandnmbr)
	s.send(chr(commandnmbr))

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
		get_wifi_networks(byte, string)
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
