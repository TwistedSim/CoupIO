import asyncio
import random
import uuid
from abc import abstractmethod

from itertools import cycle, count
from enum import Enum, auto
from typing import Dict

from socketio import exceptions


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
            # TODO: implement action arguments
            # self['args'] = args
            # self['kwargs'] = kwargs

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
            self.obfuscator = None

        @property
        def public_state(self):
            public_state = {}
            for key, val in self.state.items():
                if self.obfuscator:
                    public_state[key] = self.obfuscator(key, val)
                else:
                    public_state[key] = val
            return public_state

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
    ActionTimeout = 1.0  # Max time for the players to answer to an action

    Actions = {}

    class Event(Enum):
        Update = 'update'
        Turn = 'turn'
        Start = 'game_started'
        End = 'game_ended'

    def __init__(self, sio, owner):
        self.sio = sio
        self.owner = owner
        self.uuid = str(uuid.uuid4())
        self.players: Dict[str, Game.Player] = {}
        self.status = Game.Status.Waiting
        self.current_player = None
        self.current_action = None
        self.lock = asyncio.Lock()
        self.actions = []
        self.player_order = None
        self.pid_generator = count(0)

    async def add_player(self, sid):
        async with self.lock:
            if sid not in self.players and self.status == Game.Status.Waiting:
                # Make sure new player public id is unique in this game
                self.players[sid] = Game.Player(sid, int(next(self.pid_generator)))

    async def remove_player(self, sid):
        async with self.lock:
            if sid in self.players and self.status == Game.Status.Waiting:
                self.players.pop(sid)

    @abstractmethod
    async def next_turn(self, action, target_pid):
        raise NotImplementedError()

    @abstractmethod
    async def is_player_dead(self, target):
        raise NotImplementedError()

    async def start(self):
        await self.sio.emit(GameInterface.Event.Start.value, (self.uuid, self.nb_player))
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

        print(f'Player {self.players[winners[0]].pid} won the game.')
        await self.sio.emit(GameInterface.Event.End.value, self.players[winners[0]].pid, room=self.uuid)
        return winners[0]

    async def _next_turn(self):
        self.current_player = self.players[next(self.player_order)]
        self.current_action = None
        answer = None

        while not self.current_player.alive:
            self.current_player = self.players[next(self.player_order)]

        await self.update()

        try:
            answer = await self.sio.call(GameInterface.Event.Turn.value, to=self.current_player.sid, timeout=self.ActionTimeout)
            if len(answer) == 2:
                action, target_pid = answer
            else:
                action = answer
                target_pid = None
        except exceptions.TimeoutError:
            action = None
            target_pid = None
        except TypeError as err:
            action = None
            target_pid = None
            print(err)

        action = await self._deserialize_action(action)
        self.current_action = await self.validate_action(action, self.current_player.sid, target_pid)

        if self.current_action is None:
            await self.eliminate(self.current_player.sid, reason=f'Invalid turn response: {answer}')
        else:
            await self.next_turn(self.current_action, target_pid)

    async def update(self):
        state = {'current_player': self.current_player.pid}
        for player in self.players.values():
            state['others'] = {p.pid: {'id': p.pid, 'alive': p.alive, **p.public_state}
                               for p in self.players.values() if p.pid != player.pid}
            state['you'] = {'id': player.pid, 'alive': player.alive, **player.state}
            await self.sio.emit(GameInterface.Event.Update.value, state, room=player.sid)

    async def eliminate(self, target, invalid_action=True, reason=None):
        self.players[target].alive = False
        msg = f'Player {self.players[target].pid} was eliminated.'
        if invalid_action:
            msg = msg.strip('.')
            msg += f' for an invalid action.'
        if reason:
            msg += ' Reason: ' + reason
        print(msg)
        await self.sio.send(msg, room=self.uuid)

    @classmethod
    def deserialize_action(cls, action: dict):
        # TODO replace with custom json encoder/decoder in socketio
        if not type(action) is dict:
            return

        action_type = cls.Actions.get(action['type'])

        if not issubclass(action_type, Game.Action):
            return

        # TODO implement action arguments
        # return action_type(*action['args'], **action['kwargs'])
        return action_type()

    async def _deserialize_action(self, action: dict):
        action = self.deserialize_action(action)
        if action is None:
            await self.sio.send(f'Invalid action', room=self.current_player.sid)
        return action

    async def validate_action(self, action: Game.Action, sid, target_pid):

        if action is None:
            return
        elif target_pid is not None and target_pid not in (self.players[p].pid for p in self.players):
            await self.sio.send(f'Invalid player selected: {target_pid}', room=self.current_player.sid)
            return

        target = self.pid_to_sid(target_pid)

        if target and self.is_player_dead(target):
            await self.sio.send(f'Selected player is dead: {target_pid}', room=self.current_player.sid)
            return

        if not await action.validate(self, sid, target):
            await self.sio.send(f'Invalid action', room=self.current_player.sid)
            return

        return action

    def pid_to_sid(self, pid):
        # public id to socket id
        if pid is not None:
            return next(sid for sid in self.players if self.players[sid].pid == pid)

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
