import random

from client.bot_interface import BotInterface
from games import CoupGame
from games.Coup.actions import Coup, Duke, Captain


class DefaultBot(BotInterface):

    # Define your stuff here
    game_state = None

    def start_condition(self, nb_player):
        # Condition for a game owner to start the current game. Not use if you are not the game owner
        return nb_player > 3

    async def start(self, nb_player):
        # Raise when the game start. Initialize stuff here.
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
        # If an influence from another player is not dead, it will be shown as a generic Action
        self.game_state = game_state
        print(self.game_state, sep='\n')

    async def on_action(self, sender, target, action):
        #  answer with an action to block or to challenge, otherwise pass
        print(f'Player {sender} use {action} on {target}')

    async def on_block(self, sender, target, block_with):
        # When the action you just play is block, answer with a challenge or pass
        pass

    async def on_kill(self):
        # When one of your influence is killed, choose which one you remove
        alive_influences = [inf['action']['type'] for inf in self.game_state['you']['influences'] if inf['alive']]
        return CoupGame.Actions[random.choice(alive_influences)]()

    async def on_swap(self, cards):
        # When you win a challenge or if you use the ambassador
        pass
