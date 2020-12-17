import sys

from games.Coup.actions import Income, ForeignAid, Coup, Duke, Contessa, Captain, Assassin, Ambassador, Challenge
from games.game_interface import GameInterface, Game


class CoupGame(GameInterface):

    MinPlayer = 2
    MaxPlayer = 6

    Actions = {
        action.__name__: action
        for action in {Income, ForeignAid, Coup, Duke, Contessa, Captain, Assassin, Ambassador, Challenge}
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cards = []
        cards.extend(Duke() for _ in range(3))
        cards.extend(Captain() for _ in range(3))
        cards.extend(Assassin() for _ in range(3))
        cards.extend(Contessa() for _ in range(3))
        cards.extend(Ambassador() for _ in range(3))
        self.deck = Game.Deck(cards)

    async def start(self):
        self.deck.reset()
        for p in self.players:
            self.players[p].state['coins'] = 2
            self.players[p].state['influences'] = [[card, True] for card in self.deck.take(2)]
        await super().start()

    async def next_turn(self, action, target_pid):

        callback = None
        if type(self.current_action) in {Assassin, Captain, Ambassador, Duke, ForeignAid}:
            callback = None  # self.on_react

        await self.sio.emit(
            'action',
            data=(self.current_player.pid, target_pid, self.current_action['type']),
            room=self.uuid,
            callback=callback
        )

        # TODO implement block and challenge mecanism

        # Action is activated

        if target_pid is not None:
            print(f'Player {self.current_player.pid} use action {self.current_action} on player {target_pid}')
        else:
            print(f'Player {self.current_player.pid} use action {self.current_action}')

        await self.current_action.activate(self, self.current_player.sid, self.pid_to_sid(target_pid))

    async def kill(self, target):
        #  Shortcut if player only have one card left
        if self.player_influence_alive(target) > 1:
            selected_influence = await self.sio.call('kill', to=target)
            influence = await self.deserialize_action(selected_influence)
            if influence is not None:
                if [influence, True] in self.players[target].state['influences']:
                    idx = self.players[target].state['influences'].index([influence, True])
                    self.players[target].state['influences'][idx][1] = False
                    await self.sio.send(f'Player {self.players[target].pid} remove the {influence["type"]} from his influences', room=self.uuid)
                    print(f'Player {self.players[target].pid} removed the {influence["type"]}')
                    return
            await self.sio.send(f'Invalid influence returned: {selected_influence}', room=self.players[target].sid)
            await self.eliminate(target)
        else:
            await self.eliminate(target, invalid_action=False)

    async def swap(self, target, count):
        new_cards = ['' for _ in range(count)]  # TODO: draw cards
        # TODO: Validate selected card
        # TODO: Swap the cards
        kept_cards = await self.sio.call('swap', (self.uuid, new_cards), to=target)

    async def replace(self, target, influence):
        # TODO: replace the influence with another
        pass

    async def block(self, sid, target, influence):
        # TODO: emit on_action to others
        # TODO: check target answer, if pass, block action, otherwise, challenge
        # TODO: wait if there is a challenger before the target answer
        # return if block succeed
        pass

    async def challenge(self, sid, target, action):
        self.sio.send('Current player was challenged', room=self.uuid)
        succeed = any(inf[1] is True and type(inf[0]) is action for inf in self.players[sid].state['influences'])
        if succeed:
            await self.replace(sid, self.__class__.__name__)
            await self.kill(target)
        else:
            await self.kill(sid)

    async def eliminate(self, target, invalid_action=True):
        await super().eliminate(target, invalid_action)
        for influence in self.players[target].state['influences']:
            influence[1] = False

    def player_influence_alive(self, sid):
        return len(list(filter(lambda x: x[1] is True, self.players[sid].state['influences'])))

    def is_player_dead(self, sid):
        return self.player_influence_alive(sid) == 0
