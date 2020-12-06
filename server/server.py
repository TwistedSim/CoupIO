import socketio
import random

from game_interface import GameInterface, Game


class Server(socketio.AsyncNamespace):

    current_games = {}
    game_class = None 
    sio = None

    @classmethod
    def configure(cls, sio: socketio.Server, game: GameInterface):
        cls.game_class = game
        cls.sio = sio

    async def on_connect(self, sid, environ):
        print(f'Client {sid} connected')
        await self.sio.send(f'Connected to {Server.game_class.__name__} server', room=sid)
        await self.sio.emit('on_turn', room=sid)


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
        if len(self.sio.rooms(sid)) > 1:
            await self.sio.send(f'You already are in game {self.sio.rooms(sid)[1]}', room=sid)
        elif game_uuid not in self.current_games:
            await self.sio.send(f'Game {game_uuid} does not exists', room=sid)
        elif not self.current_games[game_uuid].is_valid():
            await self.sio.send(f'Game {game_uuid} is not available', room=sid)
        else:
            await self.current_games[game_uuid].add_player(sid)
            self.sio.enter_room(sid, game_uuid)
            await self.sio.send(f'Game {game_uuid} joined', room=sid)
            await self.sio.send(f'A new player joined the game', room=game_uuid, skip_sid=sid)
            await self.sio.emit('player_joined_game', (game_uuid, self.current_games[game_uuid].nb_player, False), room=game_uuid, skip_sid=self.current_games[game_uuid].owner)
            await self.sio.emit('player_joined_game', (game_uuid, self.current_games[game_uuid].nb_player, True), room=self.current_games[game_uuid].owner)
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
        game = self.current_games[game_uuid]

        if game.owner != sid:
            await self.sio.send(f'Only the owner of the game can start the game', room=sid)
            return
        elif not game.is_ready:
            await self.sio.send(f'You need at least 2 players to start a game', room=sid)
            return

        await game.start()
        await self.sio.send(f'Game {game.uuid} started', room=game_uuid)
        await self.sio.emit('game_started', (game.uuid, game.nb_player))
        print(f'Client {sid} start the game {game.uuid}')
