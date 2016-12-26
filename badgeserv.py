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
VERSION	= "0.1a"
addr	= ''
port	= 28000
logfile	= ""
date	= datetime.now().date()
DoW		= date.strftime("%A")
pending	= {}


'''#####
 Util functions
#####'''
def consoleWithTime(str):
	print("[{}] {}".format(datetime.now().time(), str))
cwt = consoleWithTime

'''#####
 Handler for incoming websock messages
#####'''
async def handleMessage(socket, path):
	req_type = path.strip('/').lower().split('/')[0]
	if   req_type == 'echo':
		msg = await socket.recv()
		cwt("Asked to echo the following:\n{}".format(msg))
		await socket.send(msg)
	elif req_type == 'ping':
		cwt("Ping.")
		await socket.send('{"Pong"}')
	elif req_type == 'client': pass
	elif req_type == 'admin': pass
	else:
		cwt("Unknown request mode: {}".format(path))

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
