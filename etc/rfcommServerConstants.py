VERIFY_DEVICE = 0
UPDATE_CONTROLLER = 1
GET_CONTROLLER_VERSION = 2
SET_TRANSFER_MODE = 3
GET_WIRELESS_INFORMATION = 4
CONNECT_TO_WIFI = 5
DISCONNECT_FROM_WIFI = 6
UPDATE_CONTROLLER_SETTINGS = 7
UPDATE_CONTROLLER_SERVICES = 8
ETHERNET_SETTINGS = 9
REBOOT_CONTROLLER = 254
UNKNOWN_COMMAND = 255

#Verify device
DEVICE_VERIFICATION_SUCCES = 0
DEVICE_VERIFICATION_MISSING = 1
DEVICE_VERIFICATION_INCORRECT_PASSKEY = 2

#Update controller
#level 1 codes
UPDATE_FILE_TRANSFER_CHECK = 2
UPDATE_CONTROLLER_LOCAL = 3
UPDATE_LOCAL_SUCCES = 4
#level 2 codes
UPDATE_FILE_CORRUPTED = 0
UPDATE_FILE_APROVED = 1

#get controller version
#level 1 codes
CONTROLLER_INTERNET_ACCESS_FALSE = 0
CONTROLLER_INTERNET_ACCESS_TRUE = 1
GET_SHA = 2
GET_SETTINGS_INFORMATION = 3
#level 2 codes
CONTROLLER_UPDATE_AVAILABLE = 0

#set transfer mode/receive zip
FILE_TRANSFER_ENABLED = 0
FILE_TRANSFER_COMPLETE = 1
FILE_TRANSFER_PROGRESS = 2

#get wireless information
INIT_WIRELESS_SETTINGS = 0
GET_WIFI_NETWORKS = 1
GET_CONNECTED_DEVICES = 2
INIT_AP_SETTINGS = 3

#WiFi connect results
WIFI_CONNECT_FAILED_INC_SSID = 0
WIFI_CONNECT_FAILED_INC_PW = 1
WIFI_CONNECT_SUCCES = 2
WIFI_CONNECT_FAILED_UNKNOWN = 3

#WiFi disconnect results
WIFI_DISCONNECT_FAILED = 0
WIFI_DISCONNECT_SUCCES = 1

#update controller settings
#level 1 codes
UPDATE_BLUETOOTH_SETTINGS = 0
UPDATE_WIRELESS_SETTINGS = 1

#update wireless settings
#level 2 codes
SWITCH_WIRELESS_MODE = 0
SET_AP_SETTINGS = 1

#update controller services
#level 1 codes
GET_RUNNING_SERVICES = 0
SET_SERVICE = 1

#ethernet settings
GET_ETHERNET_SETTINGS = 0
SET_ETHERNET_SETTINGS = 1
SWITCH_ETHERNET_MODE = 2