from datetime	import datetime
from enum		import Enum
from asyncio	import Task
import asyncio
import websockets
import json
import signal

'''#####
 Global variables
#####'''
addr	= ''
port	= 28000
logfile	= ""

VERSION	= "0.1a"
date	= datetime.now().date()
DoW		= date.strftime("%A")
pending	= {}
actions = ["NULL",'RECON','BGCHK','CONFIG']
connections	= {}
dummy_response = dict(
	name		= dict(first="Edward", last="Richardson"),
	badge		= "RRU-28413",
	badge_t		= "staff",
	hr_total	= 30,
	hr_worked	= 0)

'''#####
 Util functions
#####'''
def consoleWithTime(str):
	print("[{}] {}".format(datetime.now().time(), str))
cwt = consoleWithTime


'''#####
 Handler for incoming websock messages. Has four modes:
 echo	Repeats whatever the stream receives
 ping	Replies pong as a JSON object
 client	Client operations
 admin	Admin operations
#####'''
async def handleMessage(socket, path):
	req_type = path.strip('/').lower().split('/')[0]

	#####
	# Basic troubleshooting: Echo
	if   req_type == 'echo':
		msg = await socket.recv()
		cwt("Asked to echo the following:\n{}".format(msg))
		await socket.send(msg)

	#####
	# Basic troubleshooting: Ping
	elif req_type == 'ping':
		pre = datetime.now()
		await socket.ping()
		diff = datetime.now() - pre
		cwt("Ping: {}ms".format(diff.microseconds/1000))
		resp = '{{"Pong":{{"{}","{}"}}}}'.format(diff.seconds, diff.microseconds)
		await socket.send(resp)

	#####
	# Client Functionality
	elif req_type == 'client':
		cwt("New connection at {}:{}".format(socket.remote_address[0], socket.remote_address[1]))
		while socket.open:
			try:
				msg = await socket.recv()
				msgParsed = json.loads(msg)
				if msgParsed["action"] != actions[2]: raise KeyError()	#Check for malformation
				cwt("Looking up badge ID: {}".format(msgParsed["BID"]))
				if msgParsed["BID"] == "TEST":
					cwt("Sending dummy data")
					await socket.send(json.dumps(dummy_response, indent=2))
				#TODO: Get an API key and write the request code
			except websockets.exceptions.ConnectionClosed: pass
			except KeyError: cwt("Malformed client message: \n{}".format(json.dumps(msgParsed, indent=2, sort_keys=True)))
	# End Client Funtionality
	#####

	#####
	# Admin Functionality
	elif req_type == 'admin': pass
	# End Admin Functionality

	else:
		cwt("Unknown request mode: {}".format(path))
# End handleMessage
########


########
# Runs every two seconds to check if network shutdown was requested.
async def checkShutdown():
	while not shutdown:
		await asyncio.sleep(2)
	cwt("Shutting down based on network command.")
	server.close()
	loop.stop()
	cwt("shutdown")


if addr == '':	addr_human = "localhost"
else:			addr_human = addr
shutdown = False
cwt("Server v{} starting on {} ({})".format(VERSION, date, DoW))
server = websockets.serve(handleMessage, addr, port)
cwt("  Listening on {}:{}".format(addr_human, port))


#######
# Handler for SIGINT
def stoprun(a, ab):
	print()
	cwt("Shutting down based on SIGINT")
	server.close()
	loop.stop()
	exit()
signal.signal(signal.SIGINT, stoprun)


loop = asyncio.get_event_loop()
loop.run_until_complete(server)
loop.run_until_complete(checkShutdown())
loop.run_forever()
loop.close()
