from __future__ import annotations

from .action import Action, log


def _stamp(world) -> str:
    return world.clock.stamp()


class SocializeAction(Action):
    action_type = "socialize"

    def __init__(self, rng, config: dict, decision):
        super().__init__(rng, config, decision)
        self.ticks = self._int("socialize_ticks", 2)
        self.restore = self._float("social_restore", 8.0)
        self.delta = self._int("relationship_delta", 1)
        self.partner_id = decision.target_npc_id if decision is not None else None
        self._applied = False

    def can_execute(self, npc, world) -> bool:
        if not self.partner_id:
            return False
        partner = world.get_npc(self.partner_id)
        return partner is not None and partner.alive and partner.location_id == npc.location_id

    def start(self, npc, world) -> None:
        npc.last_socialize_day = world.clock.day
        partner = world.get_npc(self.partner_id)
        if partner is not None:
            log.debug(f"[{_stamp(world)}] {npc.name} started talking to {partner.name}.")

    def apply(self, npc, world) -> None:
        if self._applied:
            return
        partner = world.get_npc(self.partner_id)
        if partner is None or not partner.alive or partner.location_id != npc.location_id:
            return
        self._applied = True
        npc.needs.social = min(100.0, npc.needs.social + self.restore)
        partner.needs.social = min(100.0, partner.needs.social + self.restore * 0.5)
        npc.adjust_relationship(self.partner_id, self.delta)
        partner.adjust_relationship(npc.id, self.delta)
        if (
            npc.personality.generosity > 0.7
            and npc.has_resource("food")
            and partner.needs.hunger > 80.0
        ):
            npc.consume_resource("food", 1)
            food = world.resources["food"]
            partner.needs.hunger = max(0.0, partner.needs.hunger - food.hunger_restore)
            world.record_food_consumed(npc)
            npc.add_memory(
                _stamp(world), "shared_food", f"{npc.name} shared food with {partner.name}.", 4.0, partner.id
            )
            log.info(f"[{_stamp(world)}] {npc.name} shared food with hungry {partner.name}.")
        location_name = world.get_location(npc.location_id).name
        npc.add_memory(_stamp(world), "met_npc", f"{npc.name} talked to {partner.name} at {location_name}.", 3.0, self.partner_id)
        partner.add_memory(_stamp(world), "met_npc", f"{partner.name} talked to {npc.name} at {location_name}.", 3.0, npc.id)
        world.stats.social_interactions += 1
        log.info(f"[{_stamp(world)}] {npc.name} chatted with {partner.name} at {location_name}.")

    def is_complete(self, npc, world) -> bool:
        return self.ticks_elapsed >= self.ticks