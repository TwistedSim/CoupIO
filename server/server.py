import asyncio
import inspect
import socketio
import random

from typing import Type

from games.game_interface import GameInterface, Game


class Server(socketio.AsyncNamespace):

    current_games = {}
    game_class = None 
    sio = None
    start_lock = asyncio.Lock()

    @classmethod
    def configure(cls, sio: socketio.Server, game: Type[GameInterface]):
        cls.game_class = game
        cls.sio = sio

        server_methods = [m[0] for m in inspect.getmembers(cls, predicate=inspect.isfunction) if m[0].startswith('on_')]
        for method in inspect.getmembers(cls.game_class, predicate=inspect.ismethod):
            if method[0] in server_methods:
                raise NameError(f'A event handler for {method[0]} already exists in the server interface.')
            if method[0].startswith('on_'):
                cls.sio.on(method[0][3:], handler=method[1])

    async def on_connect(self, sid, environ):
        print(f'Client {sid} connected')
        await self.sio.send(f'Connected to {Server.game_class.__name__} server', room=sid)

    async def on_create_game(self, sid):
        new_game = self.game_class(self.sio, sid)
        self.current_games[new_game.uuid] = new_game
        await self.sio.send(f'New game created', room=sid)
        print(f'Client {sid} create a new game {new_game.uuid}')
        return new_game.uuid

    async def on_find_random_game(self, sid):
        available_games = [
            game for game in self.current_games.values() if game.is_valid]
        if available_games:
            return random.choice(available_games).uuid
        else:
            await self.sio.send(f'No game available')

    async def on_join_game(self, sid, game_uuid):
        game = self.current_games[game_uuid]
        if len(self.sio.rooms(sid)) > 1:
            await self.sio.send(f'You already are in game {self.sio.rooms(sid)[1]}', room=sid)
        elif game_uuid not in self.current_games:
            await self.sio.send(f'Game {game_uuid} does not exists', room=sid)
        elif not game.is_valid:
            await self.sio.send(f'Game {game_uuid} is not available', room=sid)
        elif game.is_full:
            await self.sio.send(f'Game {game_uuid} is full', room=sid)
        else:
            await game.add_player(sid)
            self.sio.enter_room(sid, game_uuid)
            await self.sio.send(f'Game {game_uuid} joined', room=sid)
            await self.sio.send(f'A new player joined the game', room=game_uuid, skip_sid=sid)
            await self.sio.emit('player_joined_game', (game_uuid, game.nb_player, False), room=game_uuid, skip_sid=game.owner)
            await self.sio.emit('player_joined_game', (game_uuid, game.nb_player, True), room=game.owner)
            print(f'Client {sid} join the game {game_uuid}')

    async def leave(self, sid, game_uuid):
        self.sio.leave_room(sid, game_uuid)
        await self.current_games[game_uuid].remove_player(sid)

        print(f'Client {sid} left game {game_uuid}')
        await self.sio.send(f'Left room {game_uuid}', room=sid)
        await self.sio.send('A player left the game', room=game_uuid)

        if self.current_games[game_uuid].status == Game.Status.Running:
            self.current_games[game_uuid].status = Game.Status.Aborted
        elif sid == self.current_games[game_uuid].owner:
            self.current_games[game_uuid].status = Game.Status.Aborted
            print(f'Game {game_uuid} was closed by the owner')
            await self.sio.send(f'Game {game_uuid} was close by owner', room=game_uuid)
        elif self.current_games[game_uuid].nb_player == 0:
            self.current_games[game_uuid].status = Game.Status.Aborted
            print(f'Game {game_uuid} was removed since there is no player left')

        if self.current_games[game_uuid].status == Game.Status.Aborted:
            await self.sio.send(f'Game was aborted', room=game_uuid)
            await self.sio.emit('game_aborted', game_uuid, room=game_uuid)
            await self.sio.close_room(game_uuid)

    async def on_disconnect(self, sid):
        for game in self.sio.rooms(sid):
            if game != sid:
                await self.leave(sid, game)

        print(f'Client {sid} disconnected')

    async def on_start_game(self, sid, game_uuid):
        async with self.start_lock:
            game = self.current_games[game_uuid]
            if game.owner != sid:
                await self.sio.send(f'Only the owner of the game can start the game', room=sid)
            elif not game.is_ready:
                await self.sio.send(f'The game cannot start until it is ready', room=sid)
            else:
                await self.sio.send(f'Game {game.uuid} started', room=game_uuid)
                await self.sio.emit('game_started', (game.uuid, game.nb_player))
                print(f'Client {sid} started the game {game.uuid}')
                # TODO start the game in another loop with a different socket.io namespace according to the game

                await game.start()
                print(f'Game {game.uuid} is completed.')
                await self.sio.close_room(game.uuid)


