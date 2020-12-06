from game_interface import GameInterface, Game


class Coup(GameInterface):

    async def add_player(self, sid):
        if sid not in self.players:
            self.players[sid] = {
                'coins': 0,
                'influences': None,
            }


    async def remove_player(self, sid):
        if sid in self.players:
            self.players.pop(sid)


    async def start(self):
        await super().start()
        for p in self.players:
            self.players[p]['coins'] = 2


    async def kill(self, target):
        selected_influence = await self.sio.call('kill_influence', to=target)
        if selected_influence in self.game.players[target]['influences']:
            self.game.players[target]['influences'].remove(selected_influence)


    async def swap(self, target, count):
        new_cards = ['' for _ in range(count)]  # TODO: draw cards
        # Validate selected card
        # Swap the cards
        kept_cards = await self.sio.call('swap_influence', (self.uuid, new_cards), to=target)


    async def replace(self, target, influence):
        # TODO replace the influence with another
        pass

