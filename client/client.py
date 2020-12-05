import asyncio
import time
import socketio
import argparse

loop = asyncio.get_event_loop()
sio = socketio.AsyncClient(reconnection=False)
current_bot = None

class BotInterface:

    def __init__(self, game_id=None):
        self.game_id = game_id

    def start_condition(self, nb_player):
        return nb_player > 2

    async def on_start(self, nb_player):
        print('on_start')

    async def on_aborted(self):
        pass

    async def on_end(self, is_winner):
        pass   

    async def on_turn(self):
        pass

    async def on_update(self, game_state):
        pass

    async def on_action(self, action_type):
        pass

    async def on_block(self, influence):
        pass    

    async def on_challenge(self, succeed):
        pass    


@sio.event
async def connect():
    if is_random:
        await sio.emit('find_random_game', callback=join_game)
    elif not current_game_id:
        await sio.emit('create_game', callback=join_game)
    else:
        await join_game(current_game_id)


async def join_game(game_id=None):
    if game_id:
        await sio.emit('join_game', game_id)


@sio.event
async def disconnect():  
    print(f'Disconnected')


@sio.event
async def message(msg):
    print(msg)


@sio.event
async def player_joined_game(game_uuid, nb_player, is_game_owner):
    if is_game_owner and current_bot.start_condition(nb_player):
        await sio.emit('start_game', game_uuid)


@sio.event
async def game_started(game_uuid, nb_player):
    await current_bot.on_start(nb_player)


@sio.event
async def game_aborted(game_uuid):
    await current_bot.on_aborted()
    await sio.disconnect()


async def start_client(bot: BotInterface):
    global current_bot
    current_bot = bot
    await sio.connect('http://localhost:8080')
    await sio.wait()
     

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Client to play CoupIO')
    parser.add_argument('-j', '--join', dest='joined_game_id', type=str, help='Join an existing game using the game uuid')
    parser.add_argument('-r', '--random', dest='is_random', action='store_true', help='Join a random game')

    args = parser.parse_args()
    current_game_id = args.joined_game_id
    is_random = args.is_random

    bot = BotInterface()

    try:
        loop.run_until_complete(start_client(bot))
    except RuntimeError:
        loop.run_until_complete(sio.disconnect())
