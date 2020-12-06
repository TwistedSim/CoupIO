
class BotInterface:

    def __init__(self, host, join_random_game=False, game_id=None):
        self.host = host
        self.join_random_game = join_random_game
        self.game_id = game_id

    def start_condition(self, nb_player):
        return nb_player > 2

    async def start(self, nb_player):
        pass

    async def on_turn(self):
        raise NotImplementedError()

    async def on_update(self, game_state):
        raise NotImplementedError()

    async def on_action(self, sender, target, action_type):
        raise NotImplementedError()

    async def on_block(self, influence):
        raise NotImplementedError()

    async def on_kill_influence(self):
        raise NotImplementedError()

    async def on_swap_influence(self, cards):
        raise NotImplementedError()