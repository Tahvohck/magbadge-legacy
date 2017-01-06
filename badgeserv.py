from datetime	import datetime
from enum		import Enum
from asyncio	import Task
import asyncio
import copy
import functools
import json
import re
import requests
import signal
import websockets


'''#####
 Program settings
#####'''
addr	= ''
port	= 28000
logfile	= "staging.csv"
crtfile	= "client.crt"
keyfile	= "client.key"

# Dictionary that defines the connection data that will later be exploded for requests.post()
magapiopts = dict(
	cert	= (	crtfile,
				keyfile),
	#Thankfully we don't have to worry about Content-Length in Python (Hurrah!)
	headers	= {	"Content-Type": "application/json"},
	json	= {	"jsonrpc":	"2.0",
				"method":	"barcode.lookup_attendee_from_barcode",
				"id":		"magbadgeserver-staffsuite"},
	timeout = 3,
	url = "https://onsite.uber.magfest.org:4444/jsonrpc/"
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
 Get badge information generically.
#####'''
async def getBadgeGeneric(badge, apiopts):
	badge_info = dict(r_code = 500, r_text = "Unknown server error")
	cwt("Looking up badge ID: {} via {}".format(badge, apiopts["json"]["method"]))

	apiopts["json"]["params"] = [badge]
	# Create a future that runs requests.post with the exploded copy of magapiopts as an argument.
	future_response = loop.run_in_executor(None, functools.partial(requests.post, **apiopts))
	try:
		raw_rpc_resp = await future_response
		rpc_resp = raw_rpc_resp.json()["result"]
		badge_info["name"]		= rpc_resp["full_name"]
		badge_info["badge_n"]	= rpc_resp["badge_num"]
		badge_info["badge_t"]	= rpc_resp["badge_type_label"]
		badge_info["ribbon"]	= rpc_resp["ribbon_label"]
		badge_info["hr_total"]	= rpc_resp["weighted_hours"]
		badge_info["hr_worked"]	= rpc_resp["worked_hours"]
		badge_info["r_code"]	= 200
		badge_info["r_text"]	= "Badge checked"

	except requests.exceptions.ConnectTimeout:
		cwt("Check for badge {} timed out after {} seconds".format(badge, apiopts["timeout"]))
		badge_info["r_code"] = 504
		badge_info["r_text"] = "Magfest API timed out after {} seconds.".format(apiopts["timeout"])

	except requests.exceptions.ConnectionError as e:
		cwt("Connection error to MAGAPI\n{}".format(e).replace(": ", ":\n"))
		badge_info["r_code"] = 503
		badge_info["r_text"] = "Issue connecting to MAGAPI"

	except ValueError as e:
		cwt("Failed request to MAGAPI, API response code was: {}".format(raw_rpc_resp.status_code))
		badge_info["r_code"] = 503
		badge_info["r_text"] = "MAGAPI did not return a JSON, code was: {}".format(raw_rpc_resp.status_code)

	except KeyError as e:
		cwt("Response did not have an expected key [{}]".format(e.args[0]))
		if "error" in raw_rpc_resp.json():
			rpc_resp = raw_rpc_resp.json()
			badge_info["r_text"] = "[Server error] Code: {}<br>Error: {}".format(rpc_resp["error"]["code"], rpc_resp["error"]["message"])
		elif "error" in rpc_resp:
			badge_info["r_text"] = rpc_resp["error"]
		else:
			cwt("Fallback KeyError")
			print(json.dumps(raw_rpc_resp.json(), indent=2, sort_keys=True))
			errorjson = open("json-issue-{}.error".format(datetime.now().date()), 'w')
			errorjson.write(json.dumps(raw_rpc_resp.json(), indent=2, sort_keys=True))
			errorjson.close()
		cwt(badge_info["r_text"])

	finally:
		return badge_info


'''#####
 Get badge information based on a numerical badge and form a dict based on the response
#####'''
async def getBadgeByNumber(badge):
	magapiopts_lcl = copy.deepcopy(magapiopts)		#Create a connection-local copy of the request data
	magapiopts_lcl["json"]["method"] = "attendee.lookup"
	return await getBadgeGeneric(badge, magapiopts_lcl)


'''#####
 Awaitable funtion to log badge to csv
#####'''
def logBadgeToFile(badge_info):
	entry = ""
	entry +="{},".format(str(datetime.now())[:19])
	entry +="{},".format(badge_info["badge_t"])
	entry +="{},".format(badge_info["badge_n"])
	entry +="{},".format(badge_info["name"])
	entry +="{},".format(badge_info["hr_total"])
	entry +="{}\r\n".format(badge_info["hr_worked"])
	with open("logs/{}".format(logfile), 'a') as lfile:
		lfile.write(entry)


'''#####
 Handler for incoming websock messages. Has four modes:
 echo	Repeats whatever the stream receives
 ping	Replies pong as a JSON object
 client	Client operations
 admin	Admin operations
#####'''
async def handleMessage(socket, path):
	req_type = path.strip('/').lower().split('/')[0]
	cwt("{}-mode connection opened at {}:{}".format(req_type.capitalize(), socket.remote_address[0], socket.remote_address[1]))
	while socket.open:

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

			# As long as the connection is open, wait for and act on data
			try:
				msg = await socket.recv()
				msgParsed = json.loads(msg)
				if msgParsed["action"] != actions[2]: raise KeyError()	#Check for malformation

				if msgParsed["BID"] == "TEST":
					cwt("Looking up badge ID: {}".format(msgParsed["BID"]))
					cwt("Sending dummy data")
					await socket.send(json.dumps(dummy_response, indent=2, sort_keys=True))
				else:
					#Automatically determine badge type
					if re.match(digit_regx, msgParsed["BID"]):
						badge_info = await getBadgeByNumber(msgParsed["BID"])
					else:
						badge_info = await getBadgeGeneric(msgParsed["BID"], magapiopts)

					await socket.send(json.dumps(badge_info))
					#Log to file if we were successful
					if badge_info["r_code"] == 200:
						logBadgeToFile(badge_info)

			except websockets.exceptions.ConnectionClosed: pass
			except KeyError: cwt("Malformed client message: \n{}".format(json.dumps(msgParsed, indent=2, sort_keys=True)))
		# End Client Funtionality
		#####

		#####
		# Admin Functionality
		elif req_type == 'admin': pass
		# End Admin Functionality

		else:
			cwt("Unknown request mode: {} (Closing connection)".format(path))
			break
	cwt("{}-mode connection closed at {}:{}".format(req_type.capitalize(), socket.remote_address[0], socket.remote_address[1]))
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


#######
# Handler for SIGINT
def stoprun(a, ab):
	print()
	cwt("Shutting down based on SIGINT")
	server.close()
	loop.stop()
	exit()
signal.signal(signal.SIGINT, stoprun)


#######
# Bootstrap code
VERSION    = "1.1.1"
date		= datetime.now().date()
DoW			= date.strftime("%A")
digit_regx	= '^[0-9]+$'
shutdown	= False
actions		= ["NULL",'RECON','BGCHK','CONFIG']
if addr == '':	addr_human = "localhost"
else:			addr_human = addr
# This dictionary defines the dummy reply when checking the badge "TEST"
dummy_response = dict(
	name		= "Edward Richardson",
	badge		= "RRU-28413",
	badge_t		= "staff",
	badge_n		= 765,
	hr_total	= 30,
	hr_worked	= 0,
	r_code		= 200
)

cwt("Server v{} starting on {} ({})".format(VERSION, date, DoW))
server = websockets.serve(handleMessage, addr, port)
cwt("  Listening on {}:{}".format(addr_human, port))

loop = asyncio.get_event_loop()
loop.run_until_complete(server)
loop.run_until_complete(checkShutdown())
loop.run_forever()
loop.close()
