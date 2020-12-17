from games.Coup.actions import Income, ForeignAid, Coup, Duke, Contessa, Captain, Assassin, Ambassador, Challenge
from games.game_interface import GameInterface, Game


class Influence(dict):

    def __init__(self, action: Game.Action):
        super().__init__()
        self['action'] = action
        self['alive'] = True

    @property
    def action(self):
        return self['action']

    @property
    def alive(self):
        return self['alive']

    @alive.setter
    def alive(self, value: bool):
        self['alive'] = value


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
        for action in {Duke, Contessa, Captain, Assassin, Ambassador}:
            cards.extend(action() for _ in range(3))
        self.deck = Game.Deck(cards)

    @staticmethod
    def player_obfuscator(key, val):
        if key == 'influences':
            new_value = []
            for influence in val:
                if influence.alive:
                    new_value.append(Influence(Game.Action()))
                else:
                    new_value.append(influence)
            return new_value
        else:
            return val

    async def start(self):
        self.deck.reset()
        for p in self.players:
            self.players[p].obfuscator = CoupGame.player_obfuscator
            self.players[p].state['coins'] = 2
            self.players[p].state['influences'] = [Influence(card) for card in self.deck.take(2)]
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

        # TODO implement block and challenge mechanism

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
            action = await self.deserialize_action(selected_influence)
            if action is not None:
                influences = list(map(lambda i: i.action, self.players[target].state['influences']))
                if action in influences:
                    idx = influences.index(action)
                    self.players[target].state['influences'][idx].alive = False
                    await self.sio.send(f'Player {self.players[target].pid} remove the {action["type"]} from his influences', room=self.uuid)
                    print(f'Player {self.players[target].pid} removed the {action["type"]}')
                    return
            await self.sio.send(f'Invalid influence returned: {selected_influence}', room=self.players[target].sid)
            await self.eliminate(target)
        else:
            await self.eliminate(target, invalid_action=False)

    async def swap(self, target, count):
        new_cards = list(self.deck.take(count))
        kept_cards = await self.sio.call('swap', (self.uuid, new_cards), to=target)
        # TODO: Validate selected card
        # TODO: deserialize kept card
        # TODO: Find discard card
        # TODO: replace card in deck

    async def replace(self, target, action: Game.Action):
        actions = list(map(lambda i: i.action, self.players[target].state['influences']))
        idx = actions.index(action)
        self.players[target].state['influences'][idx] = Influence(self.deck.replace(action))

    async def challenge(self, sid, target, action: Game.Action):
        self.sio.send(f'Player {self.players[sid].pid} was challenged by {self.players[target].pid}', room=self.uuid)
        succeed = any(inf.alive and type(inf.action) is type(action) for inf in self.players[sid].state['influences'])
        if succeed:
            self.sio.send(f'Player {self.players[sid].pid} won the challenge', room=self.uuid)
            await self.replace(sid, action)
            await self.kill(target)
        else:
            self.sio.send(f'Player {self.players[sid].pid} lost the challenge', room=self.uuid)
            await self.kill(sid)

    async def eliminate(self, target, invalid_action=True):
        await super().eliminate(target, invalid_action)
        for influence in self.players[target].state['influences']:
            influence.alive = False

    def player_influence_alive(self, sid):
        return len(list(filter(lambda x: x.alive, self.players[sid].state['influences'])))

    def is_player_dead(self, sid):
        return self.player_influence_alive(sid) == 0
