import asyncio
import functools
import random
from typing import Optional

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
        self.blocked_action = False
        self.is_resolved = asyncio.Event()
        self.reaction_lock = asyncio.Lock()
        self.has_answer = None
        self.challenger = None
        self.blocker = None

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
        self.blocked_action = False
        self.challenger = None
        self.blocker = None

        if target_pid is not None:
            print(f'Player {self.current_player.pid} tried to use action {self.current_action} on player {target_pid}')
        else:
            print(f'Player {self.current_player.pid} tried to use action {self.current_action}')

        target = self.pid_to_sid(target_pid)

        await self.send_action(self.current_player.sid, target, action=self.current_action)

        await self.resolve()

        if self.challenger:
            # The first reaction was a challenge
            self.blocked_action = not await self.challenge(self.challenger, self.current_player.sid, self.current_action)

        elif self.blocker:
            # The first reaction was a block
            self.blocked_action = True
            print(f'Player {self.players[self.blocker[0]].pid} tried to block player {self.current_player.pid} with {self.blocker[1]}')
            await self.send_action(self.blocker[0], self.current_player.sid, action=self.blocker[1], is_block=True)
            await self.resolve()
            if self.challenger:
                self.blocked_action = await self.challenge(self.challenger, self.blocker[0], self.blocker[1])
            else:
                print('Nobody challenged the block')
                await self.sio.send('Nobody challenged the block', room=self.uuid)
        if self.blocked_action:
            print(f'Player {self.current_player.pid} action {self.current_action} was blocked.')
            await self.sio.send(f'Player {self.current_player.pid} action {self.current_action} was blocked.', room=self.uuid)
        else:
            print(f'Player {self.current_player.pid} action {self.current_action} was activate.')
            await self.sio.send(f'Player {self.current_player.pid} action {self.current_action} was activate.', room=self.uuid)
            await self.current_action.activate(self, self.current_player.sid, self.pid_to_sid(target_pid))

    async def send_action(self, sender, target, action: Game.Action, is_block=False):
        self.has_answer = {sid: False for sid in self.alive_players if sid != self.players[sender].sid}

        players_to_send = list(self.players.keys())
        random.shuffle(players_to_send)  # Do not always ask the same player first

        event = 'block' if is_block else 'action'
        target_pid = self.players[target].pid if target else None
        sender_pid = self.players[sender].pid

        for sid in players_to_send:
            if self.players[sender].sid == sid or not self.players[sid].alive:
                await self.sio.emit(
                    event,
                    data=(sender_pid, target_pid, action),
                    to=sid
                )
            else:
                #  This is a workaround the callback that does not contains the client socket id
                await self.sio.emit(
                    event,
                    data=(sender_pid, target_pid, action),
                    to=sid,
                    callback=functools.partial(self.reaction, sid, action)
                )

    async def reaction(self, sid, current_action: Game.Action, answer: Optional[Game.Action] = None):

        self.has_answer[sid] = True
        if all(answer for answer in self.has_answer.values()):
            async with self.reaction_lock:
                self.is_resolved.set()
                return

        if answer is None:
            return

        async with self.reaction_lock:
            if self.is_resolved.is_set():
                return
            answer = await self.deserialize_action(answer)

            if answer is None:
                await self.eliminate(sid, reason='Invalid response')

            elif type(answer) is Challenge:
                if type(current_action) in {Income, ForeignAid, Coup}:  # Non-Challengeable action
                    await self.eliminate(sid, reason=f'Tried to challenge a {current_action}')
                else:
                    self.challenger = sid
                    self.is_resolved.set()

            elif type(answer) in {Captain, Duke, Contessa}:
                if self.blocker is not None:
                    await self.eliminate(sid, reason='An action was already block this turn')
                elif type(current_action) is Captain and type(answer) is Captain:
                    self.blocker = (sid, answer)
                elif type(current_action) is Captain and type(answer) is Ambassador:
                    self.blocker = (sid, answer)
                elif type(current_action) is ForeignAid and type(answer) is Duke:
                    self.blocker = (sid, answer)
                elif type(current_action) is Assassin and type(answer) is Contessa:
                    self.blocker = (sid, answer)
                else:
                    await self.eliminate(sid, reason=f'Invalid influence to block the current action {current_action}')

            else:
                await self.eliminate(sid, reason='Invalid action returned')

    async def resolve(self, timeout=1.0):
        try:
            await asyncio.wait_for(self.is_resolved.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            print('Reaction has timeout')
        finally:
            self.is_resolved.clear()

    async def kill(self, target):
        #  Shortcut if player only have one card left
        if len(self.player_influence_alive(target)) > 1:
            selected_influence = await self.sio.call('kill', to=target)
            action = await self.deserialize_action(selected_influence)
            if action is not None:
                influences = [influence.action for influence in self.players[target].state['influences']]
                if action in influences:
                    idx = influences.index(action)
                    self.players[target].state['influences'][idx].alive = False
                    await self.sio.send(f'Player {self.players[target].pid} remove the {action["type"]} from his influences', room=self.uuid)
                    print(f'Player {self.players[target].pid} removed the {action["type"]}')
                    return
            await self.sio.send(f'Invalid influence returned: {selected_influence}', room=self.players[target].sid)
            await self.eliminate(target, reason='Invalid influence returned')
        else:
            await self.eliminate(target, invalid_action=False, reason='Player have no more influence')

    async def swap(self, target, count):
        new_cards = list(self.deck.take(count))
        kept_cards = await self.sio.call('swap', (self.uuid, new_cards), to=target)
        # TODO: Validate selected card
        # TODO: deserialize kept card
        # TODO: Find discard card
        # TODO: replace card in deck

    async def replace(self, target, action: Game.Action):
        actions = [influence.action for influence in self.players[target].state['influences']]
        idx = actions.index(action)
        new_action = self.deck.replace(action)
        self.players[target].state['influences'][idx] = Influence(new_action)
        print(f'Player {self.players[target].pid} {action} was replaced with {new_action}')

    async def challenge(self, sid, target, action: Game.Action):
        #  This function return True if target won the challenge (target have the influence)
        print(f'Player {self.players[target].pid} was challenged by player {self.players[sid].pid}')
        await self.sio.send(f'Player {self.players[target].pid} was challenged by player {self.players[sid].pid}', room=self.uuid)
        succeed = any(inf.alive and type(inf.action) is type(action) for inf in self.players[target].state['influences'])
        if succeed:  # TODO inform the players the result of the challenge
            print(f'Player {self.players[target].pid} won the challenge')
            await self.sio.send(f'Player {self.players[target].pid} won the challenge', room=self.uuid)
            await self.replace(target, action)
            await self.kill(sid)
        else:
            print(f'Player {self.players[target].pid} lost the challenge')
            await self.sio.send(f'Player {self.players[target].pid} lost the challenge', room=self.uuid)
            await self.kill(target)
        return succeed

    async def eliminate(self, target, invalid_action=True, reason=None):
        await super().eliminate(target, invalid_action, reason)
        for influence in self.players[target].state['influences']:
            influence.alive = False

    @property
    def alive_players(self):
        return [p for p in self.players if self.players[p].alive]

    def player_influence_alive(self, sid):
        return [influence for influence in self.players[sid].state['influences'] if influence.alive]

    def is_player_dead(self, sid):
        return len(self.player_influence_alive(sid)) == 0
