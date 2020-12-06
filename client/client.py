import asyncio
import socketio
import inspect

from bot import BotInterface 

sio = socketio.AsyncClient(logger=True, reconnection=False)


class Client(socketio.AsyncClientNamespace):
        
    bot = None

    async def start(bot: BotInterface):
        
        Client.bot = bot

        client_methods = [m[0] for m in inspect.getmembers(Client, predicate=inspect.isfunction) if m[0].startswith('on_')]
        for method in inspect.getmembers(Client.bot, predicate=inspect.ismethod):
            print(method)
            if method[0] in client_methods:
                raise NameError(f'A event handler for {method[0]} already exists in the client interface.')
            if method[0].startswith('on_'):
                sio.event(method[1])

        await sio.connect(Client.bot.host)
        await sio.wait()
        await sio.disconnect()


    async def on_disconnect(self):
        print('Disconnected from game server')


    def on_message(self, msg):
        print(msg)


    async def on_game_aborted(self, game_uuid):
        print("Aborted client")
        await sio.disconnect()


    async def on_game_end(self, is_winner):
        pass


    async def on_connect(self):
        if Client.bot.join_random_game:
            await sio.emit('find_random_game', callback=self.join_game)
        elif not Client.bot.game_id:
            await sio.emit('create_game', callback=self.join_game)
        else:
            await join_game(Client.bot.game_id)


    async def join_game(self, game_id):
        if game_id:
            await sio.emit('join_game', game_id)
        else:
            print('No game to join')


    async def on_player_joined_game(self, game_uuid, nb_player, is_game_owner):
        if is_game_owner and Client.bot.start_condition(nb_player):
            await sio.emit('start_game', game_uuid)


sio.register_namespace(Client())