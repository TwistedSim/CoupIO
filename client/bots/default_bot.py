import random
from typing import Tuple, List

from client.bot_interface import CoupInterface
from games import CoupGame
from games.Coup.actions import Coup, Duke, Captain, Challenge, ForeignAid, Income, Assassin, Contessa, Inquisitor, \
    Ambassador
from games.game_interface import Game


class DefaultBot(CoupInterface):

    # Define your stuff here
    game_state = None

    def start_condition(self, nb_player):
        # Condition for a game owner to start the current game. Not use if you are not the game owner
        # TODO make this a command line argument
        return nb_player > 3

    async def start(self, nb_player):
        # Raise when the game start. Initialize stuff here.
        pass

    @property
    def alive_influences(self):
        if self.game_state:
            return tuple(CoupGame.deserialize_action(inf['action']) for inf in self.game_state['you']['influences'] if inf['alive'])

    @property
    def alive_players_id(self):
        if self.game_state:
            return tuple(int(p) for p in self.game_state['others'] if self.game_state['others'][p]['alive'])

    @property
    def my_player_id(self):
        if self.game_state:
            return self.game_state['you']['id']

    async def on_turn(self):
        if self.game_state['you']['coins'] >= 7:
            return Coup(), random.choice(self.alive_players_id)

        actions = [Income(), ForeignAid(), Duke(), Captain(), Ambassador(), Inquisitor()]
        if self.game_state['you']['coins'] >= 3:
            actions.append(Assassin())
        action = random.choice(actions)

        if type(action) in {Captain, Assassin}:
            target = random.choice(self.alive_players_id)
        elif type(action) is Inquisitor:
            if random.random() > 0.5:
                target = random.choice(self.alive_players_id)
            else:
                target = None
        else:
            target = None

        return action, target

    async def on_update(self, game_state):
        # If an influence from another player is not dead, it will be shown as a generic Action
        self.game_state = game_state
        # print(self.game_state, sep='\n')

    async def on_action(self, sender, target, action):
        #  answer with an action to block or to challenge, otherwise pass
        action = CoupGame.deserialize_action(action)
        if target is None:
            print(f'Player {sender} use {action["type"]}')
        else:
            print(f'Player {sender} use {action["type"]} on {target}')

        if sender == self.my_player_id:
            return

        # Randomly challenge other players:
        if random.random() > 0.8 and not type(action) in {Income, ForeignAid, Coup}:
            print(f'Challenge from {self.my_player_id}!')
            return Challenge()

        #  Randomly block ForeignAid
        if type(action) is ForeignAid:
            if random.random() > 0.9:
                return Duke()
        if type(action) is Assassin:
            if random.random() > 0.9:
                return Contessa()
        if type(action) is Captain:
            if random.random() > 0.9:
                return random.choice((Inquisitor(), Captain()))

    async def on_block(self, sender, target, block_with):
        action = CoupGame.deserialize_action(block_with)
        print(f'Player {sender} tried to block player {target} with {action}')
        # Randomly challenge block
        if random.random() > 0.9:
            return Challenge()

    async def on_kill(self):
        # When one of your influence is killed, choose which one you remove
        return random.choice(self.alive_influences)

    async def on_swap(self, target, cards: List[Game.Action]):
        # Return the card you want to discard. Do nothing with the one you want to keep.
        # if you use the ambassador or the inquisitor, the target is yourself and the cards are from the deck.
        # If target is another player, you're seeing the card of this player. Return None to force him to keep it.
        if target == self.my_player_id:
            return random.sample(cards+list(self.alive_influences), len(cards))
        else:
            return random.choice((cards[0], None))

    async def on_lookup(self):
        # When someone use the Inquisitor on you.
        return random.choice(self.alive_influences)
