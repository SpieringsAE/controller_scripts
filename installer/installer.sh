#!/bin/bash

# url to get the files and the installer
# wget -O - 

echo -e "download the service and other neccesary scripts"
git clone https://github.com/SpieringsAE/controller_scripts.git --branch $1

cp -arp /root/controller_scripts/etc /
cp -arp /root/controller_scripts/lib /
cp -arp /root/controller_scripts/usr /

apt-get install bluetooth bluez bluez-tools -y

apt install rfkill -y

apt install python3-pip -y

