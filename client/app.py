import asyncio
import time
import socketio
import argparse

from client import Client, sio
import bot


parser = argparse.ArgumentParser(description='Client to play CoupIO')

parser.add_argument('-j', '--join', dest='joined_game_id',
                    type=str, help='Join an existing game using the game uuid')

parser.add_argument('-r', '--random', dest='is_random',
                    action='store_true', help='Join a random game')

args = parser.parse_args()

# TODO register user bot from a specific folder
bot = bot.BotInterface('http://localhost:8080', args.is_random, args.joined_game_id)

loop = asyncio.get_event_loop()

try:
    loop.run_until_complete(Client.start(bot))
except RuntimeError:
    pass
