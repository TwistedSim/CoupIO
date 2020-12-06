import asyncio
import time
import socketio
import argparse

import bot_interface
from client import Client
from util import auto_discover_bots


parser = argparse.ArgumentParser(description='Client to play CoupIO')
parser.add_argument('-b', '--bot', dest='bot_name', default='DefaultBot',
                    type=str, help='Selected bot to played the game')
parser.add_argument('-j', '--join', dest='joined_game_id',
                    type=str, help='Join an existing game using the game uuid')
parser.add_argument('-r', '--random', dest='is_random',
                    action='store_true', help='Join a random game')
parser.add_argument('--host', dest='host', default='http://localhost:8080',
                    type=str, help='Address of the server')

args = parser.parse_args()
discovered_bots = auto_discover_bots()

if args.bot_name not in discovered_bots:
    raise RuntimeError(f"The bot {args.bot_name} wasn't found in the bots module. Bots found: {list(discovered_bots.keys())}")


sio = socketio.AsyncClient(reconnection=False)
sio.register_namespace(Client())

bot = discovered_bots[args.bot_name](args.host, args.is_random, args.joined_game_id)
loop = asyncio.get_event_loop()

print(f'The game will be played with {bot.__class__.__name__} on {args.host}')

try:
    Client.configure(sio, args.host, bot)
    loop.run_until_complete(Client.start())
except RuntimeError:
    pass
