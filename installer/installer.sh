#!/bin/bash

# url to get the files and the installer
# wget -O - https://raw.githubusercontent.com/SpieringsAE/controller_scripts/master/installer/installer.sh | bash -s master

echo -e "download the service and other neccesary scripts"
git clone https://github.com/SpieringsAE/controller_scripts.git --branch $1

cp -arp /root/controller_scripts/lib /
cp -arp /root/controller_scripts/usr /

apt-get install bluetooth bluez bluez-tools -y

apt install rfkill -y

apt install python3-pip -y

apt-get install libffi-dev

apt remove hostapd -y

pip3 install smbus2

pip3 install requests

pip3 install bluedot

pip3 install PyGithub

pip3 install netifaces

pip3 install pyserial

mkdir /etc/module-firmware-update

systemctl enable go-bluetooth
