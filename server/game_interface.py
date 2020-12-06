import uuid
import random

from enum import Enum, auto

class Game:

    class Status(Enum):
            Waiting = auto()
            Running = auto()
            Aborted = auto()
            Finished = auto()


    class Action:

        def __init__(self, game: 'GameInterface'):
            self.game = game


        async def validate(self, sid, target=None) -> bool:
            return True


        async def activate(self, sid, target=None):
            raise NotImplementedError()


class GameInterface:

    def __init__(self, sio, owner):
        self.sio = sio
        self.owner = owner
        self.uuid = str(uuid.uuid4())
        self.players = {}
        self.status = Game.Status.Waiting
        self.current_turn = 0
        # TODO: make deck


    async def add_player(self, sid):
        raise NotImplementedError()


    async def remove_player(self, sid):
        raise NotImplementedError()


    async def start(self):
        self.status = Game.Status.Running
        # random.shuffle(self.players)
        # TODO: Emit next turn event


    async def _next_turn(self, game_uuid):
        # TODO: Emit update to all player
        # TODO: Emit turn event to next player
        pass


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
