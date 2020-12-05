import asyncio
import time
import socketio
import argparse

loop = asyncio.get_event_loop()
sio = socketio.AsyncClient()
current_game_id = None

@sio.event
async def connect():
    if is_random:
        await sio.emit('find_random_game', callback=join_game)
    elif not current_game_id:
        await sio.emit('create_game', callback=join_game)
    else:
        await join_game(current_game_id)


@sio.event
async def disconnect():  
    print(f'Disconnected')

async def join_game(game_id):
    await sio.emit('join_game', game_id)


@sio.event
async def player_joined_game(game_uuid, nb_player, is_game_owner):
    print(game_uuid, nb_player, is_game_owner)
    if is_game_owner and nb_player > 1:
        await sio.emit('start_game', game_uuid)


@sio.event
async def message(msg):
    print(msg)


async def start_client():
    await sio.connect('http://localhost:8080')
    await sio.wait()
     

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Client to play CoupIO')
    parser.add_argument('-j', '--join', dest='joined_game_id', type=str, help='Join an existing game using the game uuid')
    parser.add_argument('-r', '--random', dest='is_random', action='store_true', help='Join a random game')

    args = parser.parse_args()
    current_game_id = args.joined_game_id
    is_random = args.is_random

    loop.run_until_complete(start_client())