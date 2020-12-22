import random

from client.bot_interface import BotInterface
from games import CoupGame
from games.Coup.actions import Coup, Duke, Captain, Challenge, ForeignAid, Income, Assassin


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
            # print(alive_players_id, self.game_state['others'])
            return Coup(), random.choice(alive_players_id)

        actions = [Income(), ForeignAid(), Duke(), Captain()]
        if self.game_state['you']['coins'] >= 3:
            actions.append(Assassin())
        action = random.choice(actions)

        if type(action) in {Captain, Assassin}:
            alive_players_id = [int(p) for p in self.game_state['others'] if self.game_state['others'][p]['alive']]
            target = random.choice(alive_players_id)
        else:
            target = None

        return action, target

    async def on_update(self, game_state):
        # If an influence from another player is not dead, it will be shown as a generic Action
        self.game_state = game_state
        # print(self.game_state, sep='\n')

    async def on_action(self, sender, target, action):
        #  answer with an action to block or to challenge, otherwise pass
        action = await CoupGame.deserialize_action(action)
        if target is None:
            print(f'Player {sender} use {action["type"]}')
        else:
            print(f'Player {sender} use {action["type"]} on {target}')

        if sender == self.game_state['you']['id']:
            return

        if target == self.game_state['you']['id']:
            influences = [await CoupGame.deserialize_action(inf['action']) for inf in self.game_state['you']['influences']]
            if (type(influences[0]) is Captain or type(influences[1]) is Captain) and type(action) is Captain:
                return Challenge()
            elif (type(influences[0]) is Duke or type(influences[1]) is Duke) and type(action) is Duke:
                return Challenge()
            elif (type(influences[0]) is Assassin or type(influences[1]) is Assassin) and type(action) is Assassin:
                return Challenge()

    async def on_block(self, sender, target, block_with):
        # When the action you just play is block, answer with a challenge or pass
        pass

    async def on_kill(self):
        # When one of your influence is killed, choose which one you remove
        alive_influences = [await CoupGame.deserialize_action(inf['action']) for inf in self.game_state['you']['influences'] if inf['alive']]
        return random.choice(alive_influences)

    async def on_swap(self, cards):
        # if you use the ambassador
        pass
