DO-Fona
============

DO-Fona is a python script that can be used to Interface with DigitalOceans API over SMS using AT Commands directly to a modem. At this time, this code is only tested with the Adafruit FONA module.

Installing
-------

Install dependencies using **pip**

    pip install -U rpi.gpio python-digitalocean pyserial

Download the latest version of the script

	wget https://github.com/riptidewave93/DO-Fona/raw/master/dofona.py
	
Update the API token in **dofona.py**, and away you go!
	
Usage
-------
Vi SMS, you can run the following commands to the unit:

	droplet create
	droplet list
	droplet destroy 
	droplet help
	
Each command has its own commands. For example, to list each region:

```
droplet list regions
```

Or to create a droplet using the Wordpress template with the name of MyBlog:

	droplet create MyBlog nyc3 wordpress 512mb

Known Bugs
------
* Properly handle multiple SMS messages at once
* Cleanup Code & standardize

ToDo/Wishlist
------
* Create a python library for interfacing with the FONA (Move away from hard calls)
* User/Session Handling
* Droplet Creation Wizard
* Support for Droplet Backups
* Support for SSH Key Management
* Support for Editing a Droplet

Notice
------
There is no warranty of any kind offered with this software. I take no responsibility for how this code is used, integrated, or modified.