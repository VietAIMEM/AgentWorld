import unittest

from world_sim.simulation.events import EventState, WorldEvent

from world_sim.tests.helpers import build_world, load_configs


def _world_with_events(events):
    import random

    from world_sim.simulation.world import World

    wc, nc = load_configs()
    world = World(wc, nc, random.Random(1))
    world.events = events
    return world


class TestWorldEvents(unittest.TestCase):
    def test_event_activates_once(self):
        event = WorldEvent(
            id="e1", type="festival", description="Festival", start_tick=10, duration_ticks=5, location_id="market"
        )
        world = _world_with_events([event])
        world.clock.tick = 10
        world.process_events()
        self.assertIs(event.state, EventState.ACTIVE)
        world.process_events()
        self.assertIs(event.state, EventState.ACTIVE)
        self.assertEqual(event.started_tick, 10)
        self.assertIn(event, world.active_events())

    def test_event_ends_and_stays_completed(self):
        event = WorldEvent(
            id="e1", type="rain", description="Rain", start_tick=10, duration_ticks=5, location_id="forest"
        )
        world = _world_with_events([event])
        world.clock.tick = 10
        world.process_events()
        self.assertIs(event.state, EventState.ACTIVE)
        world.clock.tick = 15
        world.process_events()
        self.assertIs(event.state, EventState.COMPLETED)
        self.assertNotIn(event, world.active_events())
        world.clock.tick = 50
        world.process_events()
        self.assertIs(event.state, EventState.COMPLETED)
        self.assertNotIn(event, world.active_events())

    def test_same_type_location_events_are_spaced(self):
        world = build_world()
        min_spacing = int(world.config.get("events", {}).get("min_spacing_ticks", 24))
        starts = {}
        for event in world.events:
            key = (event.type, event.location_id)
            if key in starts:
                self.assertGreaterEqual(event.start_tick - starts[key], min_spacing)
            starts[key] = event.start_tick
        self.assertGreaterEqual(len(world.events), 1)

    def test_all_events_reach_active_state(self):
        world = build_world()
        world.clock.tick = 100000
        world.process_events()
        for event in world.events:
            self.assertIs(event.state, EventState.ACTIVE)


if __name__ == "__main__":
    unittest.main()