#!/bin/sh

cp /usr/moduline/bash/go-bluetooth-start.sh /controller_scripts/usr/moduline/bash/go-bluetooth-start.sh

cp /usr/moduline/python/make-agent.py /controller_scripts/usr/moduline/python/make-agent.py

cp /lib/systemd/system/go-bluetooth.service /controller_scripts/lib/systemd/system/go-bluetooth.service

git add /controller_scripts/

git commit

git push
