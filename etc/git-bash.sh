#!/bin/sh

#display Help
Help()
{
	echo "this functions commits and pushes changes but also pulls them from github"
	echo
	echo "Syntax: scriptTemplate [-h|c|p]"
	echo "options:"
	echo "h		Displays help"
	echo "c		adds changes to staging area, commits and pushes them"
	echo "p		pulls changes from github"
	echo
}

#commit changes

Commit()
{
	cd /root/controller_scripts/

	cp /usr/moduline/bash/go-bluetooth-start.sh /root/controller_scripts/usr/moduline/bash/go-bluetooth-start.sh

	cp /usr/moduline/python/make-agent.py /root/controller_scripts/usr/moduline/python/make-agent.py

	cp /lib/systemd/system/go-bluetooth.service /root/controller_scripts/lib/systemd/system/go-bluetooth.service

	cp /etc/rfcomm-server.py /root/controller_scripts/etc/rfcomm-server.py

	cp /etc/rfcommServerConstants.py /root/controller_scripts/etc/rfcommServerConstants.py

	cp /etc/git-bash.sh /root/controller_scripts/etc/git-bash.sh

	git add /root/controller_scripts/

	git commit

	git push

	cd
}

#pull changes

Pull()
{
	cd /root/controller_scripts/

	git pull

	cp /root/controller_scripts/usr/moduline/bash/go-bluetooth-start.sh /usr/moduline/bash/go-bluetooth-start.sh

	cp /root/controller_scripts/usr/moduline/python/make-agent.py /usr/moduline/python/make-agent.py

	cp /root/controller_scripts/lib/systemd/system/go-bluetooth.service /lib/systemd/system/go-bluetooth.service

	cp /root/controller_scripts/etc/rfcomm-server.py /etc/rfcomm-server.py

	cp /root/controller_scripts/etc/rfcommServerConstants.py /etc/rfcommServerConstants.py

	cp /root/controller_scripts/etc/git-bash.sh /etc/git-bash.sh

	cd
}

##################################################################################################################
#main

while getopts ":hcp" option; do
	case $option in
		h) # display Help
			Help
			exit;;
		c) # Commit changes
			Commit
			exit;;
		p) # Pulls changes
			Pull
			exit;;
	       \?) # Invalid option
			echo "error: Invalid option"
			exit;;
	esac
done


