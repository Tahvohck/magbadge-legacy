from datetime	import datetime
from enum		import Enum
from asyncio	import Task
import asyncio
import functools
import json
import requests
import signal
import websockets


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
# This dictionary defines the dummy reply when checking the badge "TEST"
dummy_response = dict(
	name		= dict(first="Edward", last="Richardson"),
	badge		= "RRU-28413",
	badge_t		= "staff",
	badge_n		= 765,
	hr_total	= 30,
	hr_worked	= 0
)
# Dictionary that defines the connection data that will later be exploded for requests.post()
magapiopts = dict(
	cert	= (	"",""),
				#"magapi-client.crt",
				#"magapi-client.key"),
	#Thankfully we don't have to worry about Content-Length in Python (Hurrah!)
	headers	= {	"Content-Type": "application/json"},
	json	= {	"jsonrpc":	"2.0",
				"method":	"barcode.lookup_attendee_from_barcode",
				#"method":	"attendee.lookup",
				"id":		"magbadgeserver-staffsuite"},
	timeout = 3,
#	url = "https://onsite.uber.magfest.org/jsonrpc/"
	url = "https://httpbin.org/post"
)


'''#####
 Util functions
#####'''
def consoleWithTime(input):
	print("[{}] {}".format(					#[Timestamp] input
		str(datetime.now().time())[:12],	#Truncate the timestamp to HH:MM:SS.mmm
		input))								#And then the actual thing we want to print
cwt = consoleWithTime

'''#####
 Get badge information based on a scanned badge and form a dict based on the response
#####'''
async def getScannedBadgeInfo(badge):
	magapiopts_lcl = magapiopts		#Create a connection-local copy of the request data
	badge_info = dict(r_code = 500, r_text = "Unknown server error")

	#TODO: Get an API key and write the request code
	magapiopts_lcl["json"]["params"] = badge
	# Create a future that runs requests.post with the exploded copy of magapiopts as an argument.
	future_response = loop.run_in_executor(None, functools.partial(requests.post, **magapiopts_lcl))
	try:
		rpc_resp = json.loads(await future_response)
		badge_info["name"]		= rpc_resp["full_name"]
		badge_info["badge"]		= "NULL BADGE" #rpc_resp["badge_num"]
		badge_info["badge_n"]	= rpc_resp["badge_num"]
		badge_info["badge_t"]	= rpc_resp["badge_type_label"]
		badge_info["hr_total"]	= rpc_resp["weighted_hours"]
		badge_info["hr_worked"]	= rpc_resp["worked_hours"]
	except requests.exceptions.ConnectTimeout:
		cwt("Check for badge {} timed out after {} seconds".format(badge, magapiopts_lcl["timeout"]))
		badge_info["r_code"] = 504
		badge_info["r_text"] = "Magfest API timed out after {} seconds.".format(badge, magapiopts_lcl["timeout"])


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
		cwt("New client connection at {}:{}".format(socket.remote_address[0], socket.remote_address[1]))

		# As long as the connection is open, wait for and act on data
		while socket.open:
			try:
				msg = await socket.recv()
				msgParsed = json.loads(msg)
				if msgParsed["action"] != actions[2]: raise KeyError()	#Check for malformation
				cwt("Looking up badge ID: {}".format(msgParsed["BID"]))

				if msgParsed["BID"] == "TEST":
					cwt("Sending dummy data")
					await socket.send(json.dumps(dummy_response, indent=2, sort_keys=True))
				else:
					await getScannedBadgeInfo(msgParsed["BID"])

			except websockets.exceptions.ConnectionClosed: pass
			except KeyError: cwt("Malformed client message: \n{}".format(json.dumps(msgParsed, indent=2, sort_keys=True)))
		cwt("Client connection closed at {}:{}".format(socket.remote_address[0], socket.remote_address[1]))
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
