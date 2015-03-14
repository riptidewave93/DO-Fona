#!/usr/bin/env python3.4
#
# DigitalOcean FONA SMS Droplet Engine
# Created By: Chris Blake (riptidewave93)
# https://github.com/riptidewave93/DO-Fona
	
import digitalocean, logging, os, serial, sys, time, RPi.GPIO as GPIO

# DigitalOcean API Token
# You can generate a token at https://cloud.digitalocean.com/settings/tokens/new
DOToken = ''

# Set GPIO Pins
PSPin = 12
RIPin = 16
RSTPin = 18

# Serial Settings
TTL_PORT = "/dev/ttyAMA0"
TTL_SPEED = 9600

class DoFona():
	def __init__(self, PSPin, RIPin, RSTPin, TTL_PORT, TTL_SPEED, DOToken):
		#Handle args
		self.PSPin = PSPin
		self.RIPin = RIPin
		self.RSTPin = RSTPin
		self.TTL_PORT = TTL_PORT
		self.TTL_SPEED = TTL_SPEED
		self.DOToken = DOToken
		
		# Setup GPIO
		GPIO.setmode(GPIO.BOARD) # use P1 header pin numbering convention
		GPIO.setwarnings(False) # Supress Warnings
		GPIO.setup(PSPin, GPIO.IN) # Set up the GPIO channels
		GPIO.setup(RIPin, GPIO.IN)
		GPIO.setup(RSTPin, GPIO.OUT)

		# Configure logging
		self.log = logging.getLogger('DoFona')
		handler = logging.StreamHandler()
		log_format = '%(asctime)s %(name)-12s %(levelname)-8s %(message)s'
		formatter = logging.Formatter(log_format, '%b %d %H:%M:%S')
		handler.setFormatter(formatter)
		self.log.addHandler(handler)
		self.log.setLevel(logging.INFO)		

		# Start Serial
		self.ser = serial.Serial(TTL_PORT, TTL_SPEED)
		
		# Make sure FONA is setup
		self.DebugPrint('Resetting FONA device')
		self.FONAReset()

		# Delete all SMS Messages in storage
		self.DebugPrint('Erasing all SMS Messages in Storage')
		self.FONAWrite("AT+CMGD=1,4")
		
	# Debug Function. Used so we can manipulate logging later if needed
	def DebugPrint(self, msg):
		self.log.info(msg)

	# Write raw command to FONA
	def FONAWrite(self, value):
		self.DebugPrint('SerialWrite: ' + value)
		value = value + '\r\n' # Append enter
		self.ser.write(value.encode())
		time.sleep(0.5) # Always sleep so we don't overwrite

	# Write and Read to FONA
	def FONARead(self, value):
		# Start with a buffer clean
		self.ser.flushInput() 
		self.ser.flushOutput()
		self.FONAWrite(value) # Write message
		time.sleep(1) # Sleep so buffer can fill
		Resp = self.ser.read(self.ser.inWaiting()) # Pull buffer to a var, then decode
		Resp = Resp.decode() # turn to str
		Resp = '\n'.join(Resp.split('\n')[1:])# Remove first 2 lines which is the cmd and a blank line
		# Parse off ending OK and spaces	
		Resp = Resp[:Resp.rfind('\r\n')]
		Resp = Resp[:Resp.rfind('\r\n\r\n')]
		self.DebugPrint('FONARead: Raw Serial Output: ' + Resp)
		return Resp
		
	# Reset FONA Unit
	def FONAReset(self):
		self.DebugPrint('FONAReset: PIN LOW')
		GPIO.output(RSTPin, GPIO.LOW)
		time.sleep(0.1)
		self.DebugPrint('FONAReset: PIN HIGH')
		GPIO.output(RSTPin, GPIO.HIGH)
		time.sleep(6)
		self.FONAWrite("AT") # Enable Commands
		self.FONAWrite("AE0") # Disable Typing Output
		self.FONAWrite("AT+CFGRI=1") # Indicate RI Pin on SMS
		self.FONAWrite("AT+CMGF=1") # Set TXT to use TEXT input

	# Lookup latest SMS message
	def FONASMSLookup(self):
		# define vars
		Msg = ''
		Number = ''
		MsgTime = 0
		numbercount = 0;
		MsgRaw = self.FONARead("AT+CMGL=\"REC UNREAD\"") # Get message
		for magicline in MsgRaw.split("\n"): # For each line...
			self.DebugPrint('FONASMSLookup: Looping on: ' + magicline)
			#Is this the line before the message header?
			if "AT+CMGL=\"REC UNREAD\"" in magicline:
				self.DebugPrint('FONASMSLookup: on AT+CMGL=:"REC UNREAD"')
				MsgTime = 1 # Set this so we start pulling in data after this
			elif MsgTime == 1:
				# Time to parse out sender info
				self.DebugPrint('FONASMSLookup: MsgTime = 1')
				for x in magicline.split(','): # Split info into lines
					self.DebugPrint('FONASMSLookup: magicline.split = ' + x)
					# Loop through the first 2 values which we don't need
					if numbercount == 2:
						Number = x[1:-1] # Strip off "'s add to return array
						self.DebugPrint('FONASMSLookup: Sender is ' + Number)
						MsgTime = 2
						break # Leave current for loop
					else:
						numbercount += 1
			elif MsgTime == 2:
				self.DebugPrint('FONASMSLookup: MsgTime = 2')
				# Time to parse out the message
				Msg = Msg + '\n' + magicline 
		# did we get a message or no?
		if MsgTime != 2:
			self.DebugPrint('HALT! We were unable to parse a message! Restarting Self!')
			os.execv(__file__, sys.argv) # Restart self
		self.DebugPrint('FONASMSLookup: Message is ' + Msg)
		# Return info, remove the double lines also added vi the SIM800L
		return Number, Msg

	# Send an SMS
	def FONASMSSend(self, number, message):
		self.FONAWrite("AT+CMGS=\"" + number + "\"") # Send Number
		self.FONAWrite(message + "\x1A") # Send the body

	def start(self):
		self.DebugPrint("Starting DigtalOcean FONA SMS Engine")
		
		# Start Main Loop
		self.DebugPrint('Starting Listener Loop...')
		while True:
			# Is serial open?
			if self.ser.isOpen() == False:
					self.ser.Open()
			# Is the unit powered?
			if GPIO.input(PSPin) != 1:
					self.DebugPrint('SIM800L Unit is Offline! Resetting...')
					self.FONAReset()
					time.sleep(5)
					self.FONASetup()
					self.DebugPrint('SIM800L has been reset and resetup! Resuming listening...')
					continue
			# Do we have a message? GPIO will change state on message
			if GPIO.input(RIPin) != 1:
					self.DebugPrint('Message Recieved! Looking Up...')
					Sender, MessageRcvd = self.FONASMSLookup() # Lookup Message
					commands = MessageRcvd.split() # Split message into a nice dict
					# Are we a DigitalOcean command?
					if commands[0].lower() == 'droplet':
						self.DebugPrint('Droplet CMD detected!')
						# Do we have more vars or no?
						if len(commands) < 2:
							self.FONASMSSend(Sender,'Error: droplet command not defined\n\nSee droplet help for usage.')
						# Create VM
						elif commands[1].lower() == 'create':
							if len(commands) != 6:
								self.DebugPrint('Not enough build vars passed through!')
								self.FONASMSSend(Sender,'Error: missing values. Please try your command again.')
								break
							self.DebugPrint('Create VM');	
							droplet = digitalocean.Droplet(token=DOToken,
									   name=commands[2],
									   region=commands[3],
									   image=commands[4],
									   size_slug=commands[5],
									   backups=False)
							try:
								droplet.create()
							except Exception as e:
								self.DebugPrint('Build Error: ' + str(e))
								self.FONASMSSend(Sender,"We failed to Create your VM. Error response: " + str(e))
								break
							else:
								self.FONASMSSend(Sender,"Hello " + Sender + ', Spinning up your droplet! Note that the root password will be emailed to your DigitalOcean account.')
								self.DebugPrint('Waiting for VM to startup...');
								# Start loop for status checking
								done = 0
								while done == 0:
									actions = droplet.get_actions()
									for action in actions:
										action.load()
										# Once it shows complete, droplet is up and running
										if 'complete' in action.status:
											done = 1
											self.DebugPrint('VM spinup is complete!');
											droplet.load() # Reload values
											self.FONASMSSend(Sender,'Your VM was created! :D \nThe IP is ' + droplet.ip_address)
									time.sleep(2) # Let's not knock all day on the API
								self.DebugPrint('Done with build, resuming listening state...')
						# List Objects
						elif commands[1].lower() == 'list':
							self.DebugPrint('List Objects');
							# No Definition check
							if len(commands) < 3:
								self.FONASMSSend(Sender,'Error: droplet list object not defined \n\nSee droplet help for usage.')
							# Regions
							elif commands[2].lower() == 'regions':
								self.DebugPrint('Droplet List regions')
								MsgResp = ''
								# Load up management engine
								manager = digitalocean.Manager(token=DOToken)
								regions = manager.get_all_regions()
								for region in regions:
									MsgResp = MsgResp + '\n' + region.slug
								self.FONASMSSend(Sender,'Available Regions:' + MsgResp)	
							# Images
							elif commands[2].lower() == 'images':
								self.DebugPrint('Droplet List images')
								MsgResp = ''
								# Load up management engine
								manager = digitalocean.Manager(token=DOToken)
								images = manager.get_global_images()
								for image in images:
									self.DebugPrint(image.name + ' has a slug of ' + str(image.slug))
									MsgResp = MsgResp + '\n' + str(image.slug)
								self.FONASMSSend(Sender,'Available Images:' + MsgResp)	
							# Sizes
							elif commands[2].lower() == 'sizes':
								self.DebugPrint('Droplet List sizes')
								MsgResp = ''
								# Load up management engine
								manager = digitalocean.Manager(token=DOToken)
								sizes = manager.get_all_sizes()
								for size in sizes:
									MsgResp = MsgResp + '\n' + size.slug
								self.FONASMSSend(Sender,'Available Sizes:' + MsgResp)	
							# All else
							else:
								self.DebugPrint('Droplet List else catch-all')
								self.FONASMSSend(Sender,'Error: Invalid list command.\n\nSee droplet help for usage.')
						# Remove VM
						elif commands[1].lower() == 'destroy':
							instid = ''
							self.DebugPrint('Destroy VM')
							# Load up management engine
							manager = digitalocean.Manager(token=DOToken)
							my_droplets = manager.get_all_droplets()
							# For all instances lets find it by name
							for droplet in my_droplets:
								# Found our instance, aww ya
								if droplet.name.lower() == commands[2].lower():
									self.DebugPrint('Instance ' + droplet.name + ' has an ID of ' + str(droplet.id))
									instid = droplet.id
							# did we find our instance? if so remove it
							if instid == '':
								self.DebugPrint('No ID found for ' + commands[2].lower() + ', does it exist?')
								self.FONASMSSend(Sender,'Unable to find an instance with the name of ' + commands[2])
							else:
								self.DebugPrint('Starting Instance Removal')
								droplet = manager.get_droplet(instid)
								try:
									droplet.destroy()
								except Exception as e:
									self.DebugPrint('Destroy Error: ' + str(e))
									self.FONASMSSend(Sender,"We failed to destroy your VM. Error response: " + str(e))
									break
								else:
									self.FONASMSSend(Sender,droplet.name + ' has been destroyed!')
						# Help Request
						elif commands[1].lower() == 'help':
							self.DebugPrint('Help');
							self.FONASMSSend(Sender, 'Droplet Command Usage:\ndroplet create name region image size_slug\ndroplet list (regions,images,sizes)\ndroplet destroy name\ndroplet help')
						# All other cases
						else:
							self.DebugPrint('Catch-All Else Case');
							self.FONASMSSend(Sender, 'Error: please check your syntax.\n\n\n\nSee droplet help for usage.')
					else:
						self.DebugPrint('No valid command, replying with default response');
						self.FONASMSSend(Sender,"You Send Me " + MessageRcvd + '\n- Sent from DoFona!')
		
if __name__ == '__main__':
	smsfona = DoFona(PSPin,RIPin,RSTPin,TTL_PORT,TTL_SPEED,DOToken)
	smsfona.start()