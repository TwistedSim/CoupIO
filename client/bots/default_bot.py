import random

from client.bot_interface import BotInterface
from games.coup import Duke, Coup, Captain


class DefaultBot(BotInterface):

    game_state = None

    def start_condition(self, nb_player):
        return nb_player > 1

    async def start(self, nb_player):
        pass

    async def on_turn(self):
        if self.game_state['you']['coins'] >= 7:
            return Coup(), int(random.choice(list(self.game_state['others'].keys())))
        elif self.game_state['you']['coins'] >=5:
            return Captain(), int(random.choice(list(self.game_state['others'].keys())))
        else:
            return Duke(), int(random.choice(list(self.game_state['others'].keys())))

    async def on_update(self, game_state):
        print(game_state['you'])
        self.game_state = game_state

    async def on_action(self, sender, target, action):
        print(f'Player {sender} use {action} on {target}')

    async def on_block(self, sender, target, block_with):
        pass

    async def on_kill(self):
        return random.choice(self.game_state['you']['influences'])[0]['type']

    async def on_swap(self, cards):
        pass
