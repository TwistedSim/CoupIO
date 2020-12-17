import asyncio
import random
import uuid
from abc import abstractmethod

from itertools import cycle, count
from enum import Enum, auto


class Game:
    class Status(Enum):
        Waiting = auto()
        Running = auto()
        Aborted = auto()
        Finished = auto()

    class Action(dict):

        def __init__(self, *args, **kwargs):
            super().__init__()
            self['type'] = type(self).__name__
            self['args'] = args
            self['kwargs'] = kwargs

        def __str__(self):
            return type(self).__name__

        async def validate(self, game: 'GameInterface', sid, target) -> bool:
            return True

        async def activate(self, game: 'GameInterface', sid, target):
            raise NotImplementedError()

    class Player:

        def __init__(self, sid, pid):
            self.sid = sid
            self.pid = pid
            self.alive = True
            self.state = {}

    class Deck(list):

        def __init__(self, cards):
            super().__init__()
            self.cards = cards[:]
            self.reset()

        def reset(self):
            self.clear()
            self.extend(self.cards[:])
            self.shuffle()

        def take(self, n=1):
            for _ in range(n):
                yield self.pop()

        def replace(self, card):
            self.append(card)
            self.shuffle()
            return next(self.take(1))

        def shuffle(self):
            random.shuffle(self)


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
        async with self.lock:
            if sid not in self.players:
                # Make sure new player public id is unique in this game
                self.players[sid] = Game.Player(sid, int(next(self.pid_generator)))

    async def remove_player(self, sid):
        async with self.lock:
            if sid in self.players:
                self.players.pop(sid)

    @abstractmethod
    async def next_turn(self):
        raise NotImplementedError()

    async def start(self):
        async with self.lock:
            self.status = Game.Status.Running
            player_sid = list(self.players.keys())
            random.shuffle(player_sid)
            self.player_order = cycle(player_sid)
            while self.status == Game.Status.Running:
                winners = [p for p, v in self.players.items() if v.alive]
                if len(winners) == 1:
                    self.status = Game.Status.Finished
                else:
                    await self._next_turn()

        print(f'Client {winners[0]} won the game {self.uuid}')
        await self.sio.emit('game_ended', self.players[winners[0]].pid, room=self.uuid)

    async def _next_turn(self):
        self.current_player = self.players[next(self.player_order)]

        while not self.current_player.alive:
            self.current_player = self.players[next(self.player_order)]

        await self.update()
        await self.next_turn()

    async def update(self):
        state = {'current_player': self.current_player.pid}
        for player in self.players.values():
            # TODO make public and private state
            state['others'] = {p.pid: p.state for p in self.players.values() if p.pid != player.pid}
            state['you'] = player.state
            await self.sio.emit('update', state, room=player.sid)

    def pid_to_sid(self, pid):
        if pid is not None:
            return next(filter(lambda p: self.players[p].pid == pid, self.players))

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
