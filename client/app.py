import asyncio
import time
import socketio
import argparse

import importlib
import pkgutil
import inspect
import sys

from client import Client, sio
import bot_interface
import bots


def iter_namespace(ns_pkg):
    return pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + ".")


def extract_bots(bot_module):
    return [obj for name, obj in inspect.getmembers(bot_module) if inspect.isclass(obj)]


def auto_discover_bots():

    discovered_bot_files = {
        name: importlib.import_module(name)
        for finder, name, ispkg
        in iter_namespace(bots)
    }

    discovered_bots = {}
    for name, module in discovered_bot_files.items():
        for bot in extract_bots(module):
            if bot.__name__ in discovered_bots:
                print(f"WARNING: 2 bots with the same name existed ({bot.__name__} in file {name}). The bot will be overiden.")
            discovered_bots[bot.__name__] = bot

    return discovered_bots


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
    raise NameError(f"The bot {args.bot_name} wasn't found in the bots module. Bots found: {discovered_bots}")

bot = discovered_bots[args.bot_name](args.host, args.is_random, args.joined_game_id)
loop = asyncio.get_event_loop()

print(f'The game will be played with {bot.__class__.__name__} on {args.host}')

try:
    loop.run_until_complete(Client.start(bot))
except RuntimeError:
    pass
