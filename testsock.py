#!/usr/bin/env python

import asyncio
import websockets
import sys

path = ''
msg = 'Ping'
if len(sys.argv)>1: path = sys.argv[1]
if len(sys.argv)>2: msg = ' '.join(sys.argv[2:])


async def hello():
    async with websockets.connect('ws://localhost:28000/{}'.format(path)) as websocket:
        await websocket.send(msg)
        try:
            print(await websocket.recv())
        except websockets.exceptions.ConnectionClosed:
            print("Connection closed.")

asyncio.get_event_loop().run_until_complete(hello())
