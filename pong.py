#!/usr/bin/env python

import asyncio
import websockets

async def hello():
    async with websockets.connect('ws://localhost:28000/ping') as websocket:
        await websocket.send("pong")
        print(await websocket.recv())

asyncio.get_event_loop().run_until_complete(hello())
