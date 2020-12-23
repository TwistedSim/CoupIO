import asyncio
import functools
import random
from enum import Enum
from typing import Optional

from socketio import exceptions

from games.Coup.actions import Income, ForeignAid, Coup, Duke, Contessa, Captain, Assassin, Ambassador, Challenge, \
    Inquisitor
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
        for action in {Income, ForeignAid, Coup, Duke, Contessa, Captain, Assassin, Ambassador, Inquisitor, Challenge}
    }

    class Event(Enum):
        Action = 'action'
        Block = 'block'
        Kill = 'kill'
        Swap = 'swap'
        Lookup = 'lookup'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cards = []
        for action in {Duke, Contessa, Captain, Assassin, Ambassador, Inquisitor}:
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
        self.is_resolved.set()
        for p in self.players:
            self.players[p].obfuscator = self.player_obfuscator
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

        if self.challenger:
            # The first reaction was a challenge
            self.blocked_action = not await self.challenge(self.challenger, self.current_player.sid, self.current_action)

        elif self.blocker:
            # The first reaction was a block
            self.blocked_action = True
            print(f'Player {self.players[self.blocker[0]].pid} tried to block player {self.current_player.pid} with {self.blocker[1]}')

            await self.send_action(self.blocker[0], self.current_player.sid, action=self.blocker[1], is_block=True)

            if self.challenger:
                self.blocked_action = await self.challenge(self.challenger, self.blocker[0], self.blocker[1])
            else:
                print('Nobody challenged the block')
        if self.blocked_action:
            print(f'Player {self.current_player.pid} action {self.current_action} was blocked. '
                  f'Current player state: {self.current_player.state}. '
                  f'Target player state: {self.players[target].state if target else None}')
            await self.sio.send(f'Player {self.current_player.pid} action {self.current_action} was blocked.', room=self.uuid)
        else:

            try:
                print(f'Player {self.current_player.pid} action {self.current_action} is activated')
                await self.sio.send(f'Player {self.current_player.pid} action {self.current_action} is activated.', room=self.uuid)
                await self.current_action.activate(self, self.current_player.sid, self.pid_to_sid(target_pid))
                print(f'Current player state: {self.current_player.state}. '
                      f'Target player state: {self.players[target].state if target else None}')
            except Exception as ex:
                print(ex)
                await self.sio.send('An error happened in card activation', to=self.current_player.sid)

    async def send_action(self, sender, target, action: Game.Action, is_block=False):
        self.has_answer = {sid: False for sid in self.alive_players if sid != self.players[sender].sid}

        players_to_send = list(self.players.keys())
        random.shuffle(players_to_send)  # Do not always ask the same player first

        event = CoupGame.Event.Block.value if is_block else CoupGame.Event.Action.value
        target_pid = self.players[target].pid if target else None
        sender_pid = self.players[sender].pid

        self.is_resolved.clear()
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
                    callback=functools.partial(self._reaction_handler, sid, action)
                )

        try:
            await asyncio.wait_for(self.is_resolved.wait(), timeout=self.ActionTimeout)
        except asyncio.TimeoutError:
            print('Reaction has timeout')
        finally:
            print('Reaction is resolved')

    async def _reaction_handler(self, sid, current_action: Game.Action, answer: Optional[Game.Action] = None):
        self.has_answer[sid] = True

        async with self.reaction_lock:
            if answer is not None and not self.is_resolved.is_set():

                answer = self.deserialize_action(answer)

                if answer is None:
                    await self.eliminate(sid, reason='Invalid response')

                elif type(answer) is Challenge:
                    print(f'Received challenge from player {self.players[sid].pid}')
                    if type(current_action) in {Income, ForeignAid, Coup}:  # Non-Challengeable action
                        await self.eliminate(sid, reason=f'Tried to challenge a {current_action}')
                    elif self.blocker is not None:
                        print(f'Late challenge by player {self.players[sid].pid}. Action already challenged by {self.players[self.blocker[0]].pid}')
                    else:
                        self.challenger = sid
                        self.is_resolved.set()

                elif type(answer) in {Captain, Duke, Contessa, Inquisitor, Ambassador}:
                    print(f'Received block from player {self.players[sid].pid}')
                    if self.blocker is not None:
                        print(f'Late block by player {self.players[sid].pid}. Action already blocked by {self.players[self.blocker[0]].pid}')
                        # await self.eliminate(sid, reason='An action was already block this turn')
                    elif type(current_action) is Captain and type(answer) is Captain:
                        self.blocker = (sid, answer)
                    elif type(current_action) is Captain and type(answer) is Ambassador:
                        self.blocker = (sid, answer)
                    elif type(current_action) is Captain and type(answer) is Inquisitor:
                        self.blocker = (sid, answer)
                    elif type(current_action) is ForeignAid and type(answer) is Duke:
                        self.blocker = (sid, answer)
                    elif type(current_action) is Assassin and type(answer) is Contessa:
                        self.blocker = (sid, answer)
                    else:
                        await self.eliminate(sid, reason=f'Invalid influence to block the current action {current_action}')

                else:
                    await self.eliminate(sid, reason=f'Invalid action returned {answer}')

        if all(answer for answer in self.has_answer.values()):
            async with self.reaction_lock:
                self.is_resolved.set()

    async def kill(self, target):
        #  Shortcut if player only have one card left
        if len(self.player_influence_alive(target)) > 1:

            try:
                selected_influence = await self.sio.call(CoupGame.Event.Kill.value, to=target, timeout=self.ActionTimeout)
            except exceptions.TimeoutError:
                selected_influence = None

            action = self.deserialize_action(selected_influence)
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

    async def swap(self, sid, count):
        cards = tuple(self.deck.take(count))

        try:
            discarded_cards = await self.sio.call(CoupGame.Event.Swap.value, (self.players[sid].pid, cards), to=sid, timeout=self.ActionTimeout)
            if type(discarded_cards) is not tuple:
                discarded_cards = tuple(discarded_cards)
            discarded_cards = tuple(self.deserialize_action(card) for card in discarded_cards)
        except exceptions.TimeoutError:
            await self.sio.send(f'Player {self.players[sid].pid} timed out on swap answer. Random cards were selected', to=self.uuid)
            discarded_cards = tuple(random.sample(self.player_influence_alive(sid)+cards, count))

        if discarded_cards is None:
            await self.eliminate(sid, reason=f'No card return on swap. Expected {count} cards')
            self.deck.extend(cards)
            self.deck.shuffle()
            return

        print(f'Player {self.players[sid].pid} received {[str(card) for card in cards]}')
        print(f'Player {self.players[sid].pid} discarded {[str(card) for card in discarded_cards]}')

        if len(discarded_cards) != count:
            await self.eliminate(sid, reason=f'Invalid number of card returned in swap. Expected: {count}. Actual: {len(discarded_cards)}')
            self.deck.extend(cards)
            self.deck.shuffle()
            return

        possible_cards = self.player_influence_alive(sid)+cards
        match = tuple([card, False] for card in possible_cards)
        for card in discarded_cards:
            try:
                idx = match.index([card, False])
                if not match[idx][1]:
                    match[idx][1] = True
                else:
                    raise ValueError()
            except ValueError:
                await self.eliminate(sid, reason=f'Invalid card returned in swap event: {str(card)}')
                self.deck.extend(cards)
                self.deck.shuffle()
                return

        for card, discarded in match:
            self.deck.append(card)
        self.deck.shuffle()

        self.players[sid].state['influences'] = [inf for inf in self.players[sid].state['influences'] if not inf.alive]
        self.players[sid].state['influences'].extend([Influence(card) for card, discarded in match if not discarded])

    async def lookup(self, sid, target):

        if not self.players[target].alive:
            msg = f'Targeted player {self.players[target].pid} is now dead, skipping...'
            print(msg)
            self.sio.send(msg, to=self.uuid)
        try:
            card = await self.sio.call(CoupGame.Event.Lookup.value, to=target, timeout=self.ActionTimeout)
            card = self.deserialize_action(card)
            if card not in self.player_influence_alive(target):
                await self.eliminate(target, reason=f'Invalid answer to lookup event: {card}')
                return
        except exceptions.TimeoutError:
            await self.sio.send(f'Player {self.players[sid].pid} timed out on lookup event. Card was randomly choosen', to=self.uuid)
            card = random.choice(self.player_influence_alive(target))

        print(f'Player {self.players[target].pid} sent the card {str(card)}')

        try:
            replaced_card = await self.sio.call(CoupGame.Event.Swap.value, (self.players[target].pid, tuple(card)), to=sid, timeout=self.ActionTimeout)
            replaced_card = self.deserialize_action(replaced_card)
        except exceptions.TimeoutError:
            self.sio.send(f'Player {self.players[sid].pid} timed out on swap event. Card was randomly kept or replaced', to=self.uuid)
            replaced_card = random.choice(card+(None,))

        if replaced_card is None:
            print(f'Player {self.players[sid].pid} asked to keep the card')
        elif type(replaced_card) is type(card):
            print(f'Player {self.players[sid].pid} asked to replace the card')
            self.replace(target, card)
        else:
            await self.eliminate(sid, reason=f'Invalid card returned on lookup event: {replaced_card}')

    def replace(self, target, action: Game.Action):
        actions = self.player_influence_alive(target)
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
            self.replace(target, action)
            await self.kill(sid)
        else:
            print(f'Player {self.players[target].pid} lost the challenge')
            await self.sio.send(f'Player {self.players[target].pid} lost the challenge', room=self.uuid)
            await self.kill(target)
        await self.update()
        return succeed

    async def eliminate(self, target, invalid_action=True, reason=None):
        await super().eliminate(target, invalid_action, reason)
        for influence in self.players[target].state['influences']:
            influence.alive = False

    @property
    def alive_players(self):
        return tuple(p for p in self.players if self.players[p].alive)

    def player_influence_alive(self, sid):
        return tuple(influence['action'] for influence in self.players[sid].state['influences'] if influence.alive)

    def is_player_dead(self, sid):
        return len(self.player_influence_alive(sid)) == 0
