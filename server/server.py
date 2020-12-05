from aiohttp import web
import socketio

from enum import Enum, auto
import uuid

sio = socketio.AsyncServer(async_mode='aiohttp')
app = web.Application()
sio.attach(app)

current_games = {}

class Game:

    class State(Enum):
        Waiting = auto()
        Running = auto()
        Aborted = auto()
        Finished = auto()

    def __init__(self):
        self.owner = None
        self.uuid = str(uuid.uuid4())
        self.players = []
        self.state = Game.State.Waiting


    def is_valid(self):
        return len(self.players) <= 6 and self.state == Game.State.Waiting

@sio.event
async def connect(sid, environ):
    print(f'Client {sid} connected')
    await sio.send('Connected to CoupIO server', room=sid)


@sio.event
async def create_game(sid):
    new_game = Game()
    new_game.owner = sid
    current_games[new_game.uuid] = new_game
    await sio.send(f'New game created', room=sid)
    print(f'Client {sid} create a new game {new_game.uuid}')
    return new_game.uuid



@sio.event
async def start_game(sid, game_uuid): 
    game = current_games[game_uuid]
    
    if game.owner != sid:
        await sio.send(f'Only the owner of the game can start the game', room=sid)
        return
    elif len(game.players) < 2:
        await sio.send(f'You need at least 2 players to start a game', room=sid)
        return

    game.state = Game.State.Running
    print(f'Client {sid} start the game {game.uuid}')


@sio.event
async def find_random_game(sid):    
    import random
    if current_games:
        game = random.choice(list(current_games.values()))
        return game.uuid
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
        current_games[game_uuid].players.append(sid)
        sio.enter_room(sid, game_uuid)
        await sio.send(f'Game {game_uuid} joined', room=sid)
        await sio.send(f'A new player joined the game', room=game_uuid, skip_sid=sid)
        await sio.emit('player_joined_game', (game_uuid, len(current_games[game_uuid].players), False), room=game_uuid, skip_sid=current_games[game_uuid].owner)
        await sio.emit('player_joined_game', (game_uuid, len(current_games[game_uuid].players), True), room=current_games[game_uuid].owner)
        print(f'Client {sid} join the game {game_uuid}')

@sio.event
async def leave(sid, game_uuid):
    sio.leave_room(sid, game_uuid)
    print(f'Client {sid} left game {game_uuid}')
    await sio.send(f'Left room {game_uuid}', room=sid)
    await sio.send('A player left the game', room=game_uuid)

@sio.event
async def disconnect(sid):
    for game in sio.rooms(sid):
        if game != sid:
            await leave(sid, game)
            
    print(f'Client {sid} disconnected')


if __name__ == '__main__':
    web.run_app(app)