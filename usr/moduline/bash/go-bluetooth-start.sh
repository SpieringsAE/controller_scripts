#!/bin/sh
####


hciattach /dev/ttymxc0 bcm43xx 921600 flow

bluetoothctl power on

python3 /usr/moduline/python/make-agent.py
