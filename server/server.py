from aiohttp import web
import socketio

from enum import Enum, auto
import uuid
import random

sio = socketio.AsyncServer(async_mode='aiohttp')
app = web.Application()
sio.attach(app)

current_games = {}


class Game:

    class Status(Enum):
        Waiting = auto()
        Running = auto()
        Aborted = auto()
        Finished = auto()

    def __init__(self, owner):
        self.owner = owner
        self.uuid = str(uuid.uuid4())
        self.players = {}
        self.status = Game.Status.Waiting
        self.current_turn = 0

    def add_player(self, sid):
        if sid not in self.players:
            self.players[sid] = {
                'coins': 0,
                'influences': None,
            }

    def remove_player(self, sid):
        if sid in self.players:
            self.players.pop(sid)

    def start(self):
        self.status = Game.Status.Running
        for p in self.players:
            p['coins'] = 2
        random.shuffle(self.players)

    async def kill(self, sid, target):
        await sio.emit('kill_influence', room=target, callback=self.__kill_completed(target))

    async def __kill_completed(self, target):
        async def inner(selected_influence):
            # TODO test is influence is alive
            if selected_influence in self.game.players[target]['influences']:
                self.game.players[target]['influences'].remove(
                    selected_influence)
            await next_turn()
        return inner

    async def swap(self, target, count):
        new_cards = ['' for _ in range(count)]  # TODO: draw cards
        await sio.emit('swap_influence', new_cards, room=target, callback=self.__swap_completed(target, new_cards))

    async def __swap_completed(self, target, new_cards):
        async def inner(selected_card):
            # Validate selected card
            # Swap the cards
            await next_turn()
        return inner

    def replace(self, target, influence):
        pass  # TODO replace the influence with another

    @property
    def nb_player(self):
        return len(self.players)

    def state(self, sid=None):
        return {
            'current_turn': self.current_turn,
            'players': {idx: p for idx, p in enumerate(self.players.values())}
        }

    def is_valid(self):
        return self.nb_player <= 6 and self.status == Game.Status.Waiting

    def is_ready(self):
        return self.nb_player > 1 and self.status == Game.Status.Waiting


class Action:

    Blockable = False

    async def validate(self, sid, target=None) -> bool:
        return True

    async def activate(self, sid, target=None):
        raise NotImplementedError()


class Income(Action):

    async def activate(self, sid, target=None):
        self.game.players[sid]['coins'] += 1


class ForeignAid(Action):

    Blockable = True

    async def activate(self, sid, target=None):
        self.game.players[sid]['coins'] += 2


class Coup(Action):

    async def validate(self, sid, target=None) -> bool:
        return self.game.players[sid]['coins'] >= 7

    async def activate(self, sid, target):
        self.game.players[sid]['coins'] -= 7
        await self.game.kill(sid, target)


class Influence(Action):

    def __init__(self, game):
        self.game = game

    async def challenge(self, sid) -> bool:
        succeed = any(type(inf) is type(self)
                      for inf in self.game.players[sid]['influences'])
        if succeed:
            self.game.replace(sid, type(self))
        else:
            self.game.kill(sid)
        return succeed


class Duke(Influence):

    async def activate(self, sid, target=None):
        self.game.players[sid]['coins'] += 3


class Contessa(Influence):

    async def validate(self, sid, target=None) -> bool:
        return False  # This card cannot be played

    async def activate(self, sid, target=None):
        pass


class Captain(Influence):

    Blockable = True

    async def activate(self, sid, target=None):
        amount = min(2, self.game.players[target]['coins'])
        self.game.players[target]['coins'] -= amount
        self.game.players[sid]['coins'] += amount


class Assassin(Influence):

    Blockable = True

    async def validate(self, sid, target=None):
        return self.game.players[sid]['coins'] >= 3

    async def activate(self, sid, target=None):
        self.game.players[sid]['coins'] -= 3
        await self.game.kill(sid, target)


class Ambassador(Influence):

    async def validate(self, sid, target=None):
        return True

    async def activate(self, sid, target=None):
        self.game.swap(sid, 2)


@sio.event
async def connect(sid, environ):
    print(f'Client {sid} connected')
    await sio.send('Connected to CoupIO server', room=sid)


@sio.event
async def create_game(sid):
    new_game = Game(sid)
    current_games[new_game.uuid] = new_game
    await sio.send(f'New game created', room=sid)
    print(f'Client {sid} create a new game {new_game.uuid}')
    return new_game.uuid


@sio.event
async def find_random_game(sid):
    available_games = [
        game for game in current_games.values() if game.is_valid]
    if available_games:
        return random.choice(available_games).uuid
    else:
        await sio.send(f'No game available')


@sio.event
async def join_game(sid, game_uuid):
    if len(sio.rooms(sid)) > 1:
        await sio.send(f'You already are in game {sio.rooms(sid)[1]}', room=sid)
    elif game_uuid not in current_games:
        await sio.send(f'Game {game_uuid} does not exists', room=sid)
    elif not current_games[game_uuid].is_valid():
        await sio.send(f'Game {game_uuid} is not available', room=sid)
    else:
        current_games[game_uuid].add_player(sid)
        sio.enter_room(sid, game_uuid)
        await sio.send(f'Game {game_uuid} joined', room=sid)
        await sio.send(f'A new player joined the game', room=game_uuid, skip_sid=sid)
        await sio.emit('player_joined_game', (game_uuid, current_games[game_uuid].nb_player, False), room=game_uuid, skip_sid=current_games[game_uuid].owner)
        await sio.emit('player_joined_game', (game_uuid, current_games[game_uuid].nb_player, True), room=current_games[game_uuid].owner)
        print(f'Client {sid} join the game {game_uuid}')


@sio.event
async def leave(sid, game_uuid):
    sio.leave_room(sid, game_uuid)
    current_games[game_uuid].remove_player(sid)

    print(f'Client {sid} left game {game_uuid}')
    await sio.send(f'Left room {game_uuid}', room=sid)
    await sio.send('A player left the game', room=game_uuid)

    if current_games[game_uuid].status == Game.Status.Running:
        current_games[game_uuid].status = Game.Status.Aborted
    elif sid == current_games[game_uuid].owner:
        current_games[game_uuid].status = Game.Status.Aborted
        print(f'Game {game_uuid} was closed by the owner')
        await sio.send(f'Game {game_uuid} was close by owner', room=game_uuid)
    elif current_games[game_uuid].nb_player == 0:
        current_games[game_uuid].status = Game.Status.Aborted
        print(f'Game {game_uuid} was removed since there is no player left')

    if current_games[game_uuid].status == Game.Status.Aborted:
        await sio.send(f'Game was aborted', room=game_uuid)
        await sio.emit('game_aborted', game_uuid, room=game_uuid)
        await sio.close_room(game_uuid)


@sio.event
async def disconnect(sid):
    for game in sio.rooms(sid):
        if game != sid:
            await leave(sid, game)

    print(f'Client {sid} disconnected')


@sio.event
async def start_game(sid, game_uuid):
    game = current_games[game_uuid]

    if game.owner != sid:
        await sio.send(f'Only the owner of the game can start the game', room=sid)
        return
    elif not game.is_ready:
        await sio.send(f'You need at least 2 players to start a game', room=sid)
        return

    game.start()
    await sio.send(f'Game {game.uuid} started', room=sid)
    await sio.emit('game_started', (game.uuid, game.nb_player))
    print(f'Client {sid} start the game {game.uuid}')

    await update(game_uuid)


@sio.event
async def update(sid, game_uuid):
    await sio.emit(game_update, game.state)

if __name__ == '__main__':
    web.run_app(app)
