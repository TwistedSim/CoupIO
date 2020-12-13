import asyncio
import uuid

from itertools import cycle, count
from enum import Enum, auto
from random import shuffle


class Game:
    class Status(Enum):
        Waiting = auto()
        Running = auto()
        Aborted = auto()
        Finished = auto()

    class Action:

        def __init__(self, game: 'GameInterface'):
            self.game = game

        async def counter(self):
            self.game.block_action = True

        async def validate(self, sid, target) -> bool:
            return True

        async def activate(self, sid, target):
            raise NotImplementedError()

    class Player:

        def __init__(self, sid, pid):
            self.sid = sid
            self.pid = pid
            self.state = {}


class GameInterface:
    MinPlayer = 2
    MaxPlayer = 10

    def __init__(self, sio, owner):
        self.sio = sio
        self.owner = owner
        self.uuid = str(uuid.uuid4())
        self.players = {}
        self.status = Game.Status.Waiting
        self.current_player = None
        self.lock = asyncio.Lock()
        self.actions = []
        self.player_order = None
        self.pid_generator = count(0)

    async def add_player(self, sid):
        if sid not in self.players:
            # Make sure new player public id is unique in this game
            self.players[sid] = Game.Player(sid, next(self.pid_generator))

    async def remove_player(self, sid):
        if sid in self.players:
            self.players.pop(sid)

    async def next_turn(self):
        self.current_player = self.players[next(self.player_order)]
        await self.update()

    async def start(self):
        self.status = Game.Status.Running
        self.player_order = cycle(shuffle(self.players.keys()))
        await self.next_turn()

    async def update(self):
        state = {'current_player': self.current_player.pid}
        for p in self.players:
            state['others'] = {p.pid: p.public_state}
            state['you'] = p.private_state
            self.sio.emit('update', state, room=p.sid)

    @property
    def nb_player(self):
        return len(self.players)

    @property
    def is_full(self):
        return self.nb_player > self.MaxPlayer and self.status == Game.Status.Waiting

    @property
    def is_valid(self):
        return not self.is_full and self.status == Game.Status.Waiting

    @property
    def is_ready(self):
        return self.nb_player >= self.MinPlayer and self.status == Game.Status.Waiting
