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

def get_controller_version(commandnmbr, arg):
	print(arg)
	s.send(chr(commandnmbr) + open("/sys/firmware/devicetree/base/hardware", "r").read())
	#runs when phone and controller are connected triggers update button on the app in the future?

###########################################################################################

#get WiFi networks
#TODO write function to get available WiFi networks
#def get_wifi_networks()
#picks up available networks and sends them and the connection status to the app


def get_wifi_networks(commandnmbr, arg):
	#nmcli dev wifi -t (gets the list in a layout optimal for scripting)
	#formatteer data
	#s.send(netwerken)
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
		#command
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
