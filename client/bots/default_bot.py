import random

from client.bot_interface import BotInterface
from games.coup import Duke


class DefaultBot(BotInterface):

    game_state = None

    def start_condition(self, nb_player):
        return nb_player > 1

    async def start(self, nb_player):
        pass

    async def on_turn(self):
        print('event received')
        return Duke(), int(random.choice(list(self.game_state['others'].keys())))

    async def on_update(self, game_state):
        print('update')
        print(game_state)
        self.game_state = game_state

    async def on_action(self, sender, target, action):
        return

    async def on_block(self, sender, target, block_with):
        pass

    async def on_kill(self):
        pass

    async def on_swap(self, cards):
        pass

    async def on_kill_influence(self):
        pass

    async def on_swap_influence(self, cards):
        pass
