from aiohttp import web
import socketio

from games.coup import Coup
from server import Server

app = web.Application()

sio = socketio.AsyncServer(async_mode='aiohttp')
sio.register_namespace(Server())
sio.attach(app)

Server.configure(sio, Coup)

web.run_app(app)
