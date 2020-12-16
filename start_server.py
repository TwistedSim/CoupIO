from aiohttp import web
import socketio

from games import CoupGame
from server.server import Server

app = web.Application()

sio = socketio.AsyncServer(async_mode='aiohttp', logger=False)
sio.register_namespace(Server())
sio.attach(app)

Server.configure(sio, CoupGame)

web.run_app(app)
