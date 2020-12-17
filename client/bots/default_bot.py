import random

from client.bot_interface import BotInterface
from games.coup import Duke, Coup, Captain


class DefaultBot(BotInterface):

    game_state = None

    def start_condition(self, nb_player):
        return nb_player > 3

    async def start(self, nb_player):
        pass

    async def on_turn(self):

        if self.game_state['you']['coins'] >= 7:
            alive_players_id = [int(p) for p in self.game_state['others'] if self.game_state['others'][p]['alive']]
            print(alive_players_id, self.game_state['others'])
            return Coup(), random.choice(alive_players_id)

        action = random.choice([Duke(), Captain()])

        alive_players_id = [int(p) for p in self.game_state['others'] if self.game_state['others'][p]['alive']]
        return action, random.choice(alive_players_id)

    async def on_update(self, game_state):
        #print(game_state['you'])
        self.game_state = game_state

    async def on_action(self, sender, target, action):
        print(f'Player {sender} use {action} on {target}')

    async def on_block(self, sender, target, block_with):
        pass

    async def on_kill(self):
        alive_influences = [inf[0]['type'] for inf in self.game_state['you']['influences'] if inf[1] is True]
        return random.choice(alive_influences)

    async def on_swap(self, cards):
        pass
