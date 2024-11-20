import discord_notify as dn
from datetime import datetime
import os
import time
import sys
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

discord_waiting_time = 1

def discord_url():
	return "https://discord.com/api/webhooks/1300873566220193863/QW0xsLFdJHswp4XyymQuv6Uig3VzabknYgPIkqWAONYK65SmQ9NX9BexHsr8bmSbvZlE"

def init():
	global filename
	global last_discord_message
	last_discord_message = time.time()
	filename = "./logs/{}.log".format(datetime.now().strftime("%d.%m.%Y_%H:%M:%S"))
	os.system("mkdir -p logs")
	with open(filename, "w+") as _:
		pass

def log(message, end="\n"):
	with open(filename, 'a') as file:
		file.write(message + end)

def discord(message):
		notifier = dn.Notifier(discord_url())
		notifier.send(message, print_message=False)
