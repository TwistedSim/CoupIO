from abc import ABC, abstractmethod
from typing import Optional, Tuple, Union

from games.Coup.actions import Challenge
from games.game_interface import Game


class BotInterface(ABC):

    def __init__(self, host, join_random_game=False, game_id=None):
        self.host = host
        self.join_random_game = join_random_game
        self.game_id = game_id

    def start_condition(self, nb_player):
        return nb_player > 2

    async def start(self, nb_player):  # TODO add game settings
        pass

    @abstractmethod
    async def on_turn(self):
        raise NotImplementedError()

    @abstractmethod
    async def on_update(self, game_state):
        raise NotImplementedError()


class CoupInterface(BotInterface):

    @abstractmethod
    async def on_action(self, sender, target, action_type) -> Optional[Game.Action]:
        raise NotImplementedError()

    @abstractmethod
    async def on_block(self, sender, target, block_with) -> Optional[Challenge]:
        raise NotImplementedError()

    @abstractmethod
    async def on_kill(self) -> Game.Action:
        raise NotImplementedError()

    @abstractmethod
    async def on_swap(self, target, cards) -> Optional[Union[Tuple[Game.Action], Game.Action]]:
        raise NotImplementedError()

    @abstractmethod
    async def on_lookup(self) -> Game.Action:
        raise NotImplementedError()
