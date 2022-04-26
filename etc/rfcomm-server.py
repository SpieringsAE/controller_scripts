#!/usr/bin/python3
from bluedot.btcomm import BluetoothServer
import requests
from signal import pause
import subprocess
import time
import rfcommServerConstants as commands
import hashlib
from smbus2 import SMBus
from github import Github
import threading
import os
import zipfile
import netifaces as ni
import serial
from multiprocessing import Process
import multiprocessing

def md5(fname):
	hash_md5 = hashlib.md5()
	with open(fname, "rb") as f:
		for chunk in iter(lambda: f.read(4096), b""):
			hash_md5.update(chunk)
	return hash_md5.hexdigest()

def get_line(path, search_term):
	with open(path, "r") as file:
		i =0
		for line in file:
			if search_term in line:
				return i
			i += 1
		return False

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
		request_verification(commands.DEVICE_VERIFICATION_SUCCESS)
		#sleep for a bit because something goes wrong with the bluetooth messages if you dont
		time.sleep(0.5)
		#send controller version to the app because it hasnt done this upon connection due to not being verified
		update_controller(commands.UPDATE_CONTROLLER, chr(commands.CHECK_FOR_UPDATE))
	else:
		#inform the app that the entered passkey was not correct
		request_verification(commands.DEVICE_VERIFICATION_INCORRECT_PASSKEY)

#part of the verification structure but is called from multiple places
def request_verification(char):
	send(chr(commands.VERIFY_DEVICE)+chr(char))

##########################################################################################

#update controller

def update_controller(commandnmbr, arg):
	global file_urls
	level1 = ord(arg[0])
	arg = arg[1:]
	if (level1 == commands.CHECK_FOR_UPDATE):
		file_urls = []
		#check internet connection
		if (check_connection(1)):
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
				#print("commit found: ")
				#print(c.commit.author.date)
				if first_run==0:
					last_commit_sha = c.sha
					first_run += 1
				if sha == c.sha:
					break
				for file in c.files:
					if "srec" in file.filename:
						file_urls.append(file.raw_url)
			if len(file_urls) > 0:
				#print(file_urls)
				# send(chr(commandnmbr) + chr(commands.CONTROLLER_INTERNET_ACCESS_TRUE) + chr(commands.CONTROLLER_UPDATE_AVAILABLE))
				send(chr(commandnmbr) + chr(commands.CONTROLLER_INTERNET_ACCESS_FALSE) + sha)
			else:
				send(chr(commandnmbr) + chr(commands.CONTROLLER_INTERNET_ACCESS_TRUE))

		else:
			#tell the app the controller is not connected to the internet and requires an update over bluetooth
			with open("/etc/module-firmware-update/lastupdatecheck.txt", "r") as file:
				sha = file.read()
			send(chr(commandnmbr) + chr(commands.CONTROLLER_INTERNET_ACCESS_FALSE) + sha)

	elif (level1==commands.UPDATE_CONTROLLER_LOCAL):
		for url in file_urls:
			name = url.split("/")[-1]
			name = name.split("2F")[-1]
			file = requests.get(url,stream=True)
			with open("/etc/module-firmware-update/"+name,"wb") as srec:
				for chunk in file.iter_content(chunk_size=1024):
					if chunk:
						srec.write(chunk)
		send(chr(commandnmbr) + chr(commands.UPDATE_LOCAL_SUCCESS))


	
	elif (level1 == commands.UPDATE_FILE_APROVED):
		print("file was aproved")
		sha = arg
		# with open("/etc/module-firmware-update/lastupdatecheck.txt", "w") as file:
		# 	file.write(sha)
		with zipfile.ZipFile("/tmp/temporary.zip", "r") as zip_ref:
			zip_ref.extractall("/etc/module-firmware-update")
		os.remove("/tmp/temporary.zip")	
		send(chr(commandnmbr) + chr(commands.UPDATE_LOCAL_SUCCESS))
	elif (level1 == commands.UPDATE_FILE_CORRUPTED):
		print("file was corrupted")
		os.remove("/tmp/temporary.zip")


def check_connection(timeout):
	try:
		requests.head("https://www.github.com/", timeout=timeout)
		return True
	except requests.ConnectionError:
		try:
			print("could not reach github, trying google.")
			requests.head("https://www.google.com/", timeout=timeout)
			return True
		except requests.ConnectionError:
			print("could not reach google either.")
			return False
		except requests.ReadTimeout:
			print("could not reach google either.")
			return False
	except requests.ReadTimeout:
		try:
			print("could not reach github, trying google.")
			requests.head("https://www.google.com/", timeout=timeout)
			return True
		except requests.ConnectionError:
			print("could not reach google either.")
			return False
		except requests.ReadTimeout:
			print("could not reach google either.")
			return False

###########################################################################################

#file transfer
#switches between command mode and zip transfer mode.

def file_transfer(commandnmbr, arg):
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
		send(chr(commands.FILE_TRANSFER) + chr(commands.FILE_TRANSFER_PROGRESS) + chr(progress))
	#for the first packet of information the file needs to be created instead of appended
	if first_write == 1:
		with open("/tmp/temporary." + "zip", "wb") as file:
			file.write(data)
		first_write =0
		#print("receiving file")
	else:
		with open("/tmp/temporary." + "zip", "ab") as file:
			file.write(data)
	#when the last packet is received
	if file_size==os.path.getsize("/tmp/temporary.zip"):
		#set the transfer mode back to command
		transfer_mode = "command"
		#inform the app that the file has been transferred and that commands are open again
		checksum = md5("/tmp/temporary.zip")
		time.sleep(0.3)
		send(chr(commands.FILE_TRANSFER)+chr(commands.FILE_TRANSFER_COMPLETE)+checksum)
		
		#print("commands enabled")

#send(filetransfer + filetransfer state + (progress))
##########################################################################################

#ethernet settings

def ethernet_settings(commandnmbr, arg):
	path = "/etc/NetworkManager/system-connections/Wired connection static.nmconnection"
	level1 = ord(arg[0])
	global mode
	arg = arg[1:]

	if level1 == commands.INIT_ETHERNET_SETTINGS:
		#get the list of connections
		stdout = subprocess.run(["nmcli", "con"], stdout=subprocess.PIPE, text=True)
		result = stdout.stdout
		result = result.split("\n")
		for name in result:
			#get the static connection
			if "static" in name:
				#check if its active
				if "eth0" in name:
					mode= "static"
				else:
					mode= "auto"
		#get the current ip address of the eth0 interface
		try:
			ip = ni.ifaddresses("eth0")[ni.AF_INET][0]["addr"]
		except KeyError:
			ip = "no IP available"
		#get the static ip from the connection file
		with open(path, "r") as con:
			ip_line = get_line(path, "address1=")
			file = con.readlines()
			ip_static = file[ip_line].split("=")[1]
			ip_static = ip_static.split("/")[0]
		#send all gathered information plus the connection status
		send(chr(commandnmbr) + chr(commands.INIT_ETHERNET_SETTINGS) + mode + ":" + ip_static + ":" + ip + ":" + str(check_connection(1)) )


	elif level1 == commands.SET_ETHERNET_SETTINGS:
		ip_line = get_line(path, "address1=")
		with open(path, "r") as con:
			file = con.readlines()
			file[ip_line] = "address1=192.168." + arg + "/16\n"
		with open(path, "w") as con:
			con.writelines(file)
		if (mode == "static"):
			subprocess.run(["nmcli", "con", "up", "Wired connection auto"])
			time.sleep(0.5)
			subprocess.run(["nmcli", "con", "up", "Wired connection static"])
			time.sleep(0.5)
		ethernet_settings(commandnmbr, chr(commands.INIT_ETHERNET_SETTINGS) + "")


	elif level1 == commands.SWITCH_ETHERNET_MODE:
		if arg == "true":
			subprocess.run(["nmcli", "con", "mod", "Wired connection auto", "connection.autoconnect", "no"])
			subprocess.run(["nmcli", "con", "mod", "Wired connection static", "connection.autoconnect", "yes"])
			subprocess.run(["nmcli", "con", "up", "Wired connection static"])
			mode = "static"
		else:
			subprocess.run(["nmcli", "con", "mod", "Wired connection auto", "connection.autoconnect", "yes"])
			subprocess.run(["nmcli", "con", "mod", "Wired connection static", "connection.autoconnect", "no"])
			subprocess.run(["nmcli", "con", "up", "Wired connection auto"])
			mode = "auto"
		ethernet_settings(commandnmbr, chr(commands.INIT_ETHERNET_SETTINGS) + "")


##########################################################################################
 
#wireless settings

def wireless_settings(commandnmbr, arg):
	level1 = ord(arg[0])
	arg = arg[1:]


	if level1 == commands.INIT_WIRELESS_SETTINGS:
		out = subprocess.run(["nmcli", "d", "s"], stdout=subprocess.PIPE, text=True)
		status = out.stdout[:-1]
		if check_connection(1):
			connection_status = "True"
		else:
			connection_status = "False"
		try:
			ip = ni.ifaddresses("wlan0")[ni.AF_INET][0]["addr"]
		except KeyError:
			ip = "no IP available"
		if "GOcontroll-ap" in status: 
			status = "ap"
			send(chr(commands.WIRELESS_SETTINGS) + chr(commands.INIT_WIRELESS_SETTINGS) + status + ":" + connection_status + ":" + ip)
		else:
			status = "wifi"
			send(chr(commands.WIRELESS_SETTINGS) + chr(commands.INIT_WIRELESS_SETTINGS) + status + ":" + connection_status + ":" + ip)
	
	
	elif level1 == commands.GET_WIFI_NETWORKS:
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
		send(chr(commandnmbr) + chr(commands.GET_WIFI_NETWORKS) + networks)
		return


	elif level1 == commands.GET_CONNECTED_DEVICES:
		print("send connected devices")


	elif level1 == commands.INIT_AP_SETTINGS:
		path = "/etc/NetworkManager/system-connections/GOcontroll-ap.nmconnection"
		with open(path , "r") as settings:
			file = settings.readlines()
			ssid_line = get_line(path, "ssid=")
			psk_line = get_line(path, "psk=")
			ssid = file[ssid_line].split("=")[1][:-1]
			psk = file[psk_line].split("=")[1][:-1]
		send(chr(commandnmbr) + chr(commands.INIT_AP_SETTINGS) + ssid + ":" + psk)


	elif level1 == commands.CONNECT_TO_WIFI:
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
			connection_result = commands.WIFI_CONNECT_SUCCESS
		elif (resultstring.find("Secrets")!=-1):
			connection_result = commands.WIFI_CONNECT_FAILED_INC_PW
			subprocess.run(["nmcli", "connection", "delete", "id", message_list[0]])
		elif (resultstring.find("SSID")!=-1):
			connection_result = commands.WIFI_CONNECT_FAILED_INC_SSID
			subprocess.run(["nmcli", "connection", "delete", "id", message_list[0]])
		else:
			connection_result = commands.WIFI_CONNECT_FAILED_UNKNOWN
			subprocess.run(["nmcli", "connection", "delete", "id", message_list[0]])
		#give feedback to the app
		send(chr(commandnmbr) + chr(commands.CONNECT_TO_WIFI) + chr(connection_result))

	
	elif level1 == commands.DISCONNECT_FROM_WIFI:
		#attempt to disconnect from specified network
		result = subprocess.run(["nmcli", "connection", "delete", "id", arg], stdout=subprocess.PIPE, text=True)
		#save the result
		resultstring = result.stdout
		#possible results:
		#Connection 'name' (uuid) succesfully deleted.
		#Error: unknown connection 'name'.\n
		#Error: cannot delete unknown connection(s): id 'name'
		if (resultstring.find("successfully")!=-1):
			disconnection_result = commands.WIFI_DISCONNECT_SUCCESS
		else:
			disconnection_result = commands.WIFI_DISCONNECT_FAILED
		#give feedback to the app
		send(chr(commandnmbr) + chr(commands.DISCONNECT_FROM_WIFI) + chr(disconnection_result))


	
	elif level1 == commands.SWITCH_WIRELESS_MODE:
		stdout = subprocess.run(["nmcli", "-t", "con"], stdout=subprocess.PIPE, text=True)
		stdout = stdout.stdout[:-1].split("\n")
		wifi_connections = []
		for i, con in enumerate(stdout):
			if "wireless" in con:
				if "GOcontroll-ap" not in con:
					wifi_connections.append(con.split(":")[0])

		if arg == "ap":
			for con in wifi_connections:
				subprocess.run(["nmcli", "con", "mod", con, "connection.autoconnect", "no"])
			subprocess.run(["nmcli", "con", "mod", "GOcontroll-ap", "connection.autoconnect", "yes"])
			stdout = subprocess.run(["nmcli", "con", "up", "GOcontroll-ap"], stdout=subprocess.PIPE, text=True)
			result = stdout.stdout
			if "successfully" in result:
				send(chr(commandnmbr) + chr(commands.SWITCH_WIRELESS_MODE) + "ap")
			else:
				send(chr(commandnmbr) + chr(commands.SWITCH_WIRELESS_MODE) + "error")
		elif arg == "wifi":
			for con in wifi_connections:
				subprocess.run(["nmcli", "con", "mod", con, "connection.autoconnect", "yes"])
			subprocess.run(["nmcli", "con", "mod", "GOcontroll-ap", "connection.autoconnect", "no"])
			stdout = subprocess.run(["nmcli", "con", "down", "GOcontroll-ap"], stdout=subprocess.PIPE, text=True)
			result = stdout.stdout
			if "successfully" in result:
				send(chr(commandnmbr) + chr(commands.SWITCH_WIRELESS_MODE) + "wifi")
			else:
				send(chr(commandnmbr) + chr(commands.SWITCH_WIRELESS_MODE) + "error")


	

##########################################################################################

def access_point_settings(commandnmbr, arg):
	level1 = ord(arg[0])
	arg = arg[1:]


	if level1 == commands.SET_AP_SETTINGS:
		arg = arg.split(":")
		name = arg[0]
		psk = arg[1]
		name_line = get_line("/etc/NetworkManager/system-connections/GOcontroll-ap.nmconnection", "ssid=")
		psk_line = get_line("/etc/NetworkManager/system-connections/GOcontroll-ap.nmconnection", "psk=")			
		with open("/etc/NetworkManager/system-connections/GOcontroll-ap.nmconnection", "r") as ap:
			file = ap.readlines()
			file[name_line] = "ssid="+name+"\n"
			file[psk_line] = "psk="+psk+"\n"
		with open("/etc/NetworkManager/system-connections/GOcontroll-ap.nmconnection", "w") as ap:
			ap.writelines(file)
		subprocess.run(["systemctl", "restart", "NetworkManager"])
		send(chr(commandnmbr) + chr(commands.SET_AP_SETTINGS) + "done")


	elif level1 == commands.INIT_AP_SETTINGS:
		path = "/etc/NetworkManager/system-connections/GOcontroll-ap.nmconnection"
		with open(path , "r") as settings:
			file = settings.readlines()
			ssid_line = get_line(path, "ssid=")
			psk_line = get_line(path, "psk=")
			ssid = file[ssid_line].split("=")[1][:-1]
			psk = file[psk_line].split("=")[1][:-1]
		send(chr(commandnmbr) + chr(commands.INIT_AP_SETTINGS) + ssid + ":" + psk)

##########################################################################################

def controller_settings(commandnmbr, arg):
	level1 = ord(arg[0])
	arg = arg[1:]


	if level1 == commands.SET_CONTROLLER_SETTINGS:
		if "GOcontroll" in arg:
			write_device_name(arg)
		else:
			arg = "GOcontroll-" + arg
			write_device_name(arg)

	
	elif (level1 == commands.INIT_CONTROLLER_SETTINGS):
		#open up the files that contain the versions
		with open("/sys/firmware/devicetree/base/hardware", "r") as file:
			hardware_version = file.read()
		with open("/root/version.txt", "r") as file:
			software_version = file.read(6)
		with open("/etc/machine-info", "r") as file:
			controller_name = file.read().split("=")
		#return the versions to the app
		send(chr(commandnmbr) + chr(commands.INIT_CONTROLLER_SETTINGS) + hardware_version + ":" + software_version + ":" + controller_name[1])


def write_device_name(name):
	with open("/etc/machine-info", "w") as file:
		file.write("PRETTY_HOSTNAME="+name)

##########################################################################################

def controller_programs(commandnmbr, arg):
	level1 = ord(arg[0])
	arg = arg[1:]

	if level1 == commands.INIT_CONTROLLER_PROGRAMS:
		statusses = []
		services = arg.split("\n")[1].split(":")
		for service in services:
			stdout = subprocess.run(["systemctl", "is-active", service], stdout=subprocess.PIPE, text=True)
			status = stdout.stdout[:-1]
			statusses.append(status)
		send(chr(commandnmbr)+chr(commands.INIT_CONTROLLER_PROGRAMS) + ":".join(statusses))
	
	
	elif level1 == commands.SET_CONTROLLER_PROGRAMS:
		data = arg.split("\n")[1].split(":")
		service = data[-1]
		new_states = data[:-1]
		if len(data)>2:
			for new_state in new_states:
				subprocess.run(["systemctl", new_state, service])
		else:
			subprocess.run(["systemctl", data[0], data[1]])

##########################################################################################

def wwan_settings(commandnmbr, arg):
	level1 = ord(arg[0])
	arg = arg[1:]


	if level1 == commands.INIT_WWAN_SETTINGS:
		net_status = [str(check_connection(1))]
		#preset variables incase not all information sources are available
		mmcli_info = ["Info not available"]
		sim_number = ["Info not available"]
		#get status of go-wwan service
		stdout = subprocess.run(["systemctl", "is-active", "go-wwan"], stdout=subprocess.PIPE, text=True)
		status = [stdout.stdout[:-1]]
		#gather info from the nmconnection file
		path = "/etc/NetworkManager/system-connections/GO-celular.nmconnection"
		pin_line = get_line(path, "pin=")
		apn_line = get_line(path, "apn=")
		with open(path, "r") as con:
			file = con.readlines()
			pin = [file[pin_line].split("=")[1][:-1]]
			apn = [file[apn_line].split("=")[1][:-1]]
		if status[0] == "active":
			modem = subprocess.run(["mmcli", "--list-modems"], stdout=subprocess.PIPE, text=True)
			modem = modem.stdout
			if "/freedesktop/" in modem:
				modem_number = modem.split("/")[-1].split(" ")[0]
				#gather modemmanager information
				try:
					mmcli = subprocess.Popen(("mmcli", "-K", "--modem="+modem_number), stdout=subprocess.PIPE)
					output = subprocess.check_output(("egrep", "model|signal-quality.value|imei|operator-name"), stdin=mmcli.stdout)
					mmcli.wait()
					mmcli_info = output[:-1].decode("utf-8").split("\n")
					for i, info in enumerate(mmcli_info):
						mmcli_info[i] = info.split(":")[1][1:]
				except subprocess.CalledProcessError:
					print("unable to get information from modemmanager")
			#gather info from the modem over serial
			at_result = sim_at_command("AT+CICCID\r", timeout=2)
			if at_result == "Error":
				at_result = "Unable to get SIM number"
			else:
				sim_number = [at_result.split(" ")[1].split("\r")[0]]
		#combine all of the data
		status_array = net_status+status+mmcli_info+pin+apn+sim_number
		send(chr(commandnmbr) + chr(commands.INIT_WWAN_SETTINGS) + ":".join(status_array))


	elif level1 == commands.SWITCH_WWAN:
		arg = arg.split(":")
		if arg[0] == "false":
			print("stopping go-wwan")
			subprocess.run(["systemctl", "stop", "go-wwan"])
			subprocess.run(["systemctl", "disable", "go-wwan"])
		else:
			if arg[1] == "false":
				print("starting go-wwan")
				subprocess.run(["systemctl", "enable", "go-wwan"])
				subprocess.run(["systemctl", "start", "go-wwan"])
			else: #service failed so needs to restart instead of start
				print("restarting go-wwan")
				subprocess.run(["systemctl", "restart", "go-wwan"])
		send(chr(commandnmbr) + chr(commands.SWITCH_WWAN))



	elif level1 == commands.SET_WWAN_SETTINGS:
		arg = arg.split(":")
		#arg = [pin,apn]
		path = "/etc/NetworkManager/system-connections/GO-celular.nmconnection"
		pin_line = get_line(path, "pin=")
		apn_line = get_line(path, "apn=")
		with open(path, "r") as con:
			file = con.readlines()
			file[pin_line] = "ssid="+arg[0]+"\n"
			file[apn_line] = "psk="+arg[1]+"\n"
		with open(path, "w") as con:
			con.writelines(file)
		send(chr(commandnmbr) + chr(commands.SET_WWAN_SETTINGS))

		
def sim_at_command(command, timeout=2):
	recv_end, send_end = multiprocessing.Pipe(False)
	ts = Process(target=read_serial_CICCID, args=(send_end,))
	ts.start()
	time.sleep(1)
	ser.write(bytes(command, "utf-8"))
	time.sleep(timeout)
	if ts.is_alive():
		ts.terminate()
		return "Error"
	else:
		result = recv_end.recv()
		return result
	

def read_serial_CICCID(send_end):
	message_finished = False
	while message_finished == False:
		try:
			response = ser.readline().decode("utf-8")
			if "+ICCID:" in response:
				final_response = response
			if "OK" in response:
				send_end.send(final_response)
				break
			if "ERR" in response:
				send_end.send("Error")
				break
		except UnicodeDecodeError:
			send_end.send("Error")
			break

##########################################################################################

#manage can settings

def can_settings(commandnmbr, arg):
	global read_can_bus_load
	level1 = ord(arg[0])
	arg = arg[1:]
	if level1 == commands.INIT_CAN_SETTINGS:
		read_can_bus_load = False
		print("Gathering can info")
		path = "/etc/network/interfaces"
		can_ifs_string = ""

		ip_a_info = subprocess.run(["ip", "-br", "a"], stdout=subprocess.PIPE, text=True)
		ip_a_info = ip_a_info.stdout
		ip_a_info_arr = ip_a_info.split("\n")
		for i in range(4):
			baudrate = "0"
			can_if = "|"
			if f"can{i}" in ip_a_info:
				can_if = "_"
				index = [idx for idx, s in enumerate(ip_a_info_arr) if f"can{i}" in s][0]
				if "UP" in ip_a_info_arr[index]:
					can_if = "-"
				baudrate = get_baudrate(i)
				baudrate = int(int(baudrate)/1000)
			can_ifs_string = f"{can_ifs_string}{can_if}:{baudrate} kBit/s\n"
		can_ifs_string = can_ifs_string[:-1]
		send(chr(commandnmbr) + chr(commands.INIT_CAN_SETTINGS)+can_ifs_string)

	
	elif level1 ==commands.SET_CAN_BAUDRATE:
		#arg= "interface:baudrate(int):state(up or down)"
		arg = arg.split(":")
		path = "/etc/network/interfaces"
		search_string = f"iface {arg[0]} inet manual"
		interface_line = get_line(path, search_string)
		if interface_line is not False:
			with open(path, "r") as interfaces:
				file = interfaces.readlines()
			line = file[interface_line+1]
			line = line.split(" ")
			line[8] = arg[1]
			line = " ".join(line)
			file[interface_line+1] = line
			with open(path, "w") as interfaces:
				interfaces.writelines(file)
			if arg[2] == "up":
				subprocess.run(["ifdown", arg[0]])
				time.sleep(0.2)
				subprocess.run(["ifup", arg[0]])
		send(chr(commandnmbr) + chr(commands.SET_CAN_BAUDRATE))



	elif level1 == commands.CAN_BUS_LOAD:
		time.sleep(1)
		interfaces = arg.split(":")
		for i,interface in enumerate(interfaces):
			interfaces[i] = f"can{interface}@"+get_baudrate(interface)
		interfaces = [":".join(interfaces)]
		read_can_bus_load = not read_can_bus_load
		if read_can_bus_load:
			ts = threading.Thread(target=bus_load_process, args=(interfaces))
			ts.start()


	elif level1 == commands.SET_CAN_STATE:
		read_can_bus_load = False
		arg = arg.split(":")
		if arg[1] == "true":
			subprocess.run(["ifup", arg[0]])
		else:
			subprocess.run(["ifdown", arg[0]])
		send(chr(commandnmbr) + chr(commands.SET_CAN_STATE))
			

def bus_load_process(interfaces):
	if len(interfaces) >1:
		interfaces = interfaces.split(":")
	busload = subprocess.Popen(["canbusload"]+interfaces, stdout=subprocess.PIPE, text=True)		
	while True:
		output = busload.stdout.readline()
		if busload.poll() is not None or read_can_bus_load == False:
			break
		if output:
			output_split = output.strip().split(" ")
			if len(output_split) > 1:
				interface = output_split[0].split("@")[0]
				load = output_split[-1]
				send(chr(commands.CAN_SETTINGS) + chr(commands.CAN_BUS_LOAD) + interface + ":" + load)
				time.sleep(0.1)


def get_baudrate(x):
	path = "/etc/network/interfaces"
	search_string = f"iface can{x} inet manual"
	interface_line = get_line(path, search_string)
	if interface_line is not False:
		with open(path, "r") as interfaces:
			file = interfaces.readlines()
		line = file[interface_line+1]
		line = line.split(" ")
		return line[8]
	return "0"

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
		#request_verification
		return
	elif byte == commands.UPDATE_CONTROLLER:
		update_controller(byte, string)
		return
	elif byte == commands.FILE_TRANSFER:
		file_transfer(byte, string)
		#receive_zip
		return
	elif byte == commands.ETHERNET_SETTINGS:
		ethernet_settings(byte,string)
		return
	elif byte == commands.WIRELESS_SETTINGS:
		wireless_settings(byte, string)
		return
	elif byte == commands.AP_SETTINGS:
		access_point_settings(byte, string)
		return
	elif byte == commands.CONTROLLER_SETTINGS:
		controller_settings(byte, string)
		return
	elif byte == commands.CONTROLLER_PROGRAMS:
		controller_programs(byte, string)
		return
	elif byte == commands.WWAN_SETTINGS:
		wwan_settings(byte, string)
		return
	elif byte == commands.CAN_SETTINGS:
		can_settings(byte, string)
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

def status_led_on():
	direction = 0
	brightness = 0
	while 1 == 1:
		time.sleep(0.01)
		if direction == 0:
			brightness += 1
		else:
			brightness -= 1
		with SMBus(2) as bus:
			bus.write_i2c_block_data(address,0x0D,[brightness])
		if brightness == 127:
			direction = 1
		if brightness == 0:
			direction = 0
			if kill_threads:
				break
def status_led_gocontroll():
	while 1==1:
		with SMBus(2) as bus:
			bus.write_i2c_block_data(address, 0x0D, [0])
			bus.write_i2c_block_data(address, 0x0B, [165])
			bus.write_i2c_block_data(address, 0x0C, [50])
		if(kill_threads):
			break
		time.sleep(0.5)
		with SMBus(2) as bus:
			bus.write_i2c_block_data(address, 0x0D, [0])
			bus.write_i2c_block_data(address, 0x0B, [0])
			bus.write_i2c_block_data(address, 0x0C, [0])
		time.sleep(0.5)
		

#slightly expanded s.send function so not every command has to convert the string to bytes
def send(string):
	print("out:")
	print(bytes(string, 'utf-8'))
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
			#get message till stopbyte
			data = data.split(bytes([255]))[0]
			#run through the commands list
			command_list(first_byte, data)
		else:
			#process raw data
			receive_zip(data)
	else:
		request_verification(commands.DEVICE_VERIFICATION_MISSING)

#function that gets called when a device connects to the server
def when_client_connects():
	global read_can_bus_load
	global tf
	global kill_threads
	read_can_bus_load = False
	kill_threads = False
	with SMBus(2) as bus:
		bus.write_i2c_block_data(address,23,[255])
		bus.write_i2c_block_data(address,0,[64])
		tf = threading.Thread(target=status_led_gocontroll)
		tf.start()
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
			update_controller(commands.UPDATE_CONTROLLER, chr(commands.CHECK_FOR_UPDATE))
			return
		#if not request verification
		else:
			request_verification(commands.DEVICE_VERIFICATION_MISSING)

#function that gets called when a device disconnects from the server
def when_client_disconnects():
	global kill_threads
	kill_threads=True
	print("connection lost")

#defines a variable which can be interacted with for bluetooth functions
#sets up callback functions and how the received/sent data is processed
s = BluetoothServer(data_received, True, "hci0", 1, None, False, when_client_connects, when_client_disconnects)
global address
address = 20
ser = serial.Serial(port='/dev/ttymxc1', 
	baudrate=115200)

pause()
