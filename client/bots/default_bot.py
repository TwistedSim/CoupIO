from client.bot_interface import BotInterface


class DefaultBot(BotInterface):

    def start_condition(self, nb_player):
        return nb_player > 1

    async def start(self, nb_player):
        pass

    async def on_turn(self):
        return  # Action, target

    async def on_update(self, game_state):
        pass

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
