
import socketio
import inspect

from client.bot_interface import BotInterface


class Client(socketio.AsyncClientNamespace):
    bot = None
    sio = None
    host = None

    @classmethod
    def configure(cls, sio: socketio.AsyncClient, host: str, bot: BotInterface):

        cls.bot = bot
        cls.sio = sio
        cls.host = host

        client_methods = [m[0] for m in inspect.getmembers(cls, predicate=inspect.isfunction) if m[0].startswith('on_')]
        for method in inspect.getmembers(cls.bot, predicate=inspect.ismethod):
            if method[0] in client_methods:
                raise NameError(f'A event handler for {method[0]} already exists in the client interface.')
            if method[0].startswith('on_'):
                cls.sio.event(method[1])

    @classmethod
    async def start(cls):
        await cls.sio.connect(cls.host)
        await cls.sio.wait()
        await cls.sio.disconnect()

    @staticmethod
    async def on_disconnect():
        print('Disconnected from game server')

    @staticmethod
    def on_message(msg):
        print(msg)

    async def on_game_start(self, *args):
        await self.bot.start(*args)

    async def on_game_aborted(self, game_uuid):
        await self.disconnect()

    @staticmethod
    async def on_game_end(is_winner):
        if is_winner:
            print('Yon won the game.')
        else:
            print('You lost the game.')

    async def on_connect(self):
        # TODO add a bot name
        if self.bot.join_random_game:
            await self.sio.emit('find_random_game', callback=self.join_game)
        elif not self.bot.game_id:
            await self.sio.emit('create_game', callback=self.join_game)
        else:
            await self.join_game(self.bot.game_id)

    async def join_game(self, game_id):
        if game_id:
            await self.sio.emit('join_game', game_id)
        else:
            print('No game to join')

    async def on_player_joined_game(self, game_uuid, nb_player, is_game_owner):
        if is_game_owner and self.bot.start_condition(nb_player):
            await self.sio.emit('start_game', game_uuid)
