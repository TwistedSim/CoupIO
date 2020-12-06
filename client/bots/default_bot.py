
import bot_interface

class DefaultBot(bot_interface.BotInterface):

    def __init__(self, host, join_random_game=False, game_id=None):
        self.host = host
        self.join_random_game = join_random_game
        self.game_id = game_id

    def start_condition(self, nb_player):
        return nb_player > 1

    async def start(self, nb_player):
        pass

    async def on_turn(self):
        pass

    async def on_update(self, game_state):
        pass

    async def on_action(self, sender, target, action_type):
        pass

    async def on_block(self, influence):
        pass

    async def on_kill_influence(self):
        pass

    async def on_swap_influence(self, cards):
        pass
