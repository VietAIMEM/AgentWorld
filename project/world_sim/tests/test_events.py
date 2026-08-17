import unittest

from world_sim.simulation.events import EventState, WorldEvent
from world_sim.simulation.simulation import Simulation

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


class TestEventSchedulingHorizon(unittest.TestCase):
    def _events(self, days, seed=42):
        wc, nc = load_configs()
        sim = Simulation(wc, nc, seed=seed, days=days, print_report=False)
        return sim.world.events

    def _total_ticks(self, days):
        return days * 24 * (60 // 10)

    def test_30_day_simulation_schedules_events_within_horizon(self):
        events = self._events(30)
        self.assertGreaterEqual(len(events), 1)
        for event in events:
            self.assertGreaterEqual(event.start_tick, 0)
            self.assertLess(event.start_tick, self._total_ticks(30))

    def test_90_day_simulation_schedules_events_within_horizon(self):
        events = self._events(90)
        self.assertGreaterEqual(len(events), 1)
        for event in events:
            self.assertGreaterEqual(event.start_tick, 0)
            self.assertLess(event.start_tick, self._total_ticks(90))

    def test_events_scheduled_beyond_day_30(self):
        events = self._events(90)
        beyond = [e for e in events if e.start_tick >= self._total_ticks(30)]
        self.assertGreater(len(beyond), 0)
        for event in beyond:
            self.assertLess(event.start_tick, self._total_ticks(90))

    def test_365_day_simulation_schedules_events_across_full_horizon(self):
        events = self._events(365)
        self.assertGreaterEqual(len(events), 1)
        for event in events:
            self.assertGreaterEqual(event.start_tick, 0)
            self.assertLess(event.start_tick, self._total_ticks(365))
        self.assertGreater(len([e for e in events if e.start_tick >= self._total_ticks(90)]), 0)

    def test_deterministic_scheduling_with_same_seed(self):
        def snapshot(seed):
            return sorted(
                (e.type, e.location_id, e.start_tick, e.duration_ticks, e.id) for e in self._events(90, seed)
            )

        self.assertEqual(snapshot(42), snapshot(42))
        self.assertEqual(snapshot(1), snapshot(1))

    def test_no_duplicate_events(self):
        events = self._events(90)
        ids = [e.id for e in events]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(events), len({(e.type, e.location_id, e.start_tick) for e in events}))


if __name__ == "__main__":
    unittest.main()