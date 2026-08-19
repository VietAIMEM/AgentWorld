"""Localhost transport between the authoritative Python simulation and Unity.

Design:

- ``SnapshotStore``: thread-safe holder of the latest presentation payload.
- ``SnapshotHTTPServer``: stdlib HTTP server on localhost serving
  ``GET /snapshot`` (latest payload), ``GET /healthz``, and
  ``POST /control`` (play / pause / step / reset). Unity is a polling HTTP
  client; the simulation never blocks on network I/O.
- ``ManagedSimulation``: runs a plain ``Simulation`` tick-by-tick in a
  background thread (replicating ``Simulation.run``'s exact
  ``update_time(); _tick()`` sequence so RNG/state evolve identically),
  publishing a snapshot after every tick. Controls (play/pause/step/reset)
  only affect the runner through ``control()`` — the explicit transport API
  boundary. When no client is connected the runner behaves exactly like a
  normal simulation.

Simulation/AI systems never import this module. It consumes zero simulation
RNG: it only reads state through ``animate`` and serializes JSON.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

from ..npc.llm import build_llm_layer
from ..simulation.simulation import Simulation
from .player import COMMAND_TYPES, PlayerCommandError, PlayerSession
from .snapshot import build_payload, serialize_payload

VALID_CONTROL_ACTIONS = ("play", "pause", "step", "reset")


class SnapshotStore:
    """Thread-safe holder of the latest snapshot payload."""

    def __init__(self):
        self._lock = threading.Lock()
        self._snapshot = None

    def publish(self, payload: dict) -> None:
        with self._lock:
            self._snapshot = payload

    def latest(self) -> Optional[dict]:
        with self._lock:
            return self._snapshot


class _Handler(BaseHTTPRequestHandler):
    def _send_json(self, status, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/snapshot":
            payload = self.server.store.latest()
            if payload is None:
                self._send_json(503, {"error": "no snapshot yet"})
                return
            body = serialize_payload(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/healthz":
            self._send_json(200, {"ok": True, "server": "npc_ai_snapshot"})
            return
        if self.path == "/interaction":
            payload = self.server.runner.interaction_payload()
            body = serialize_payload(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._send_json(404, {"error": "not found"})

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_POST(self):
        if self.path not in ("/control", "/command"):
            self._send_json(404, {"error": "not found"})
            return
        try:
            body = self._read_json_body()
        except (ValueError, json.JSONDecodeError):
            self._send_json(400, {"error": "bad request body"})
            return
        if not isinstance(body, dict):
            self._send_json(400, {"error": "request body must be a JSON object"})
            return
        if self.path == "/control":
            action = body.get("action")
            if action not in VALID_CONTROL_ACTIONS:
                self._send_json(400, {"error": f"unknown action {action!r}"})
                return
            self.server.runner.control(action)
            self._send_json(200, {"ok": True, "action": action})
            return
        # /command
        ctype = body.get("type")
        if ctype not in COMMAND_TYPES:
            self._send_json(400, {"error": f"unknown command type {ctype!r}"})
            return
        try:
            result = self.server.runner.handle_command(body)
        except PlayerCommandError as exc:
            self._send_json(200, {"ok": False, "error": str(exc)})
            return
        self._send_json(200, result)

    def log_message(self, format, *args):  # noqa: A002 - silence request logging
        pass


class SnapshotHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def start_snapshot_server(store: SnapshotStore, runner=None, host="127.0.0.1", port=8770):
    """Start a snapshot HTTP server thread. Returns the server."""
    server = SnapshotHTTPServer((host, port), _Handler)
    server.store = store
    server.runner = runner
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


class ManagedSimulation:
    """Authoritative simulation driven tick-by-tick with transport controls.

    ``_one_tick`` replicates ``Simulation.run``'s loop body exactly
    (``world.update_time()`` then ``sim._tick()``), so the RNG stream and
    final state are byte-identical to a plain ``Simulation.run``.
    """

    def __init__(self, world_config, npcs_config, seed=42, days=30, store=None, llm=None):
        self._world_config = world_config
        self._npcs_config = npcs_config
        self._seed = int(seed)
        self._days = days
        self._store = store if store is not None else SnapshotStore()
        self._lock = threading.Lock()
        self.llm = llm if llm is not None else build_llm_layer(world_config)
        self.session = PlayerSession(
            llm_bridge=self.llm.player_bridge if self.llm is not None else None
        )
        self._sim = Simulation(
            world_config, npcs_config, seed=seed, days=days, print_report=False
        )
        self._paused = False
        self._step_requested = False
        self._reset_requested = False
        self._stop = False
        self._ticks_done = 0
        self._total_ticks = self._compute_total_ticks()

    def _compute_total_ticks(self):
        if self._days is None:
            return None
        tick_minutes = self._sim.world.clock.tick_minutes or 10
        return self._days * 24 * (60 // tick_minutes)

    @property
    def store(self) -> SnapshotStore:
        return self._store

    @property
    def simulation(self) -> Simulation:
        return self._sim

    def _build_sim(self):
        return Simulation(
            self._world_config,
            self._npcs_config,
            seed=self._seed,
            days=self._days,
            print_report=False,
        )

    def control(self, action: str) -> None:
        if action not in VALID_CONTROL_ACTIONS:
            raise ValueError(f"unknown control action {action!r}")
        with self._lock:
            if action == "play":
                self._paused = False
            elif action == "pause":
                self._paused = True
            elif action == "step":
                self._paused = True
                self._step_requested = True
            elif action == "reset":
                self._reset_requested = True

    def handle_command(self, command: dict) -> dict:
        """Validate and apply an authoritative player command (session only)."""
        with self._lock:
            return self.session.handle_command(self._sim, command)

    def interaction_payload(self) -> dict:
        """Latest versioned player-interaction payload for the Unity client."""
        with self._lock:
            if self.llm is not None:
                self.llm.poll()
            payload = self.session.build_interaction_payload(self._sim)
            if self.llm is not None:
                payload["chatter"] = self.llm.store.recent(5)
            return payload

    def stop(self) -> None:
        with self._lock:
            self._stop = True
        if self.llm is not None:
            self.llm.shutdown()

    def _one_tick(self) -> None:
        world = self._sim.world
        world.update_time()
        self._sim._tick()
        self._store.publish(build_payload(self._sim))
        if self.llm is not None:
            self.llm.observe(self._sim)

    def _run_loop(self) -> None:
        while True:
            with self._lock:
                stop = self._stop
                if self._reset_requested:
                    self._reset_requested = False
                    self._sim = self._build_sim()
                    self.session = PlayerSession(
                        llm_bridge=self.llm.player_bridge if self.llm is not None else None
                    )
                    self._ticks_done = 0
                    self._total_ticks = self._compute_total_ticks()
                    self._paused = False
                step = self._step_requested
                self._step_requested = False
                paused = self._paused
            if stop:
                return
            if self._total_ticks is not None and self._ticks_done >= self._total_ticks:
                return
            if paused and not step:
                time.sleep(0.002)
                continue
            self._one_tick()
            self._ticks_done += 1

    def run(self) -> None:
        """Run in a background thread until ``days`` complete or ``stop()``."""
        thread = threading.Thread(target=self._run_loop, daemon=True)
        thread.start()
        return thread


def run_with_transport(
    world_config,
    npcs_config,
    seed=42,
    days=30,
    host="127.0.0.1",
    port=8770,
    start_server=True,
):
    """Start a managed simulation + snapshot server. Returns (runner, server)."""
    store = SnapshotStore()
    runner = ManagedSimulation(world_config, npcs_config, seed=seed, days=days, store=store)
    server = None
    if start_server:
        server = start_snapshot_server(store, runner, host=host, port=port)
    runner.run()
    return runner, server


def main(argv=None):
    """CLI: python -m world_sim.presentation.transport [--seed 42] [--days 0] [--port 8770]

    ``--days 0`` runs indefinitely (live visualization mode).
    """
    import argparse
    import json as _json
    from pathlib import Path as _Path

    parser = argparse.ArgumentParser(description="NPC simulation snapshot transport server")
    parser.add_argument("--config", default=None, help="world config JSON (defaults to world_sim/config/world.json)")
    parser.add_argument("--npcs", default=None, help="npcs config JSON (defaults to world_sim/config/npcs.json)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--days", type=int, default=0, help="0 = run indefinitely")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8770)
    args = parser.parse_args(argv)

    cfg_dir = _Path(__file__).resolve().parents[1] / "config"
    wc_path = _Path(args.config) if args.config else cfg_dir / "world.json"
    nc_path = _Path(args.npcs) if args.npcs else cfg_dir / "npcs.json"
    wc = _json.loads(wc_path.read_text(encoding="utf-8"))
    nc = _json.loads(nc_path.read_text(encoding="utf-8"))

    wc["world_generation"]["enabled"] = True
    wc["world_generation"]["seed"] = wc["world_generation"].get("seed", args.seed)
    wc["settlement_economy"]["enabled"] = True
    wc["behavior"] = {
        "enabled": True,
        "routines": {"enabled": True, "default_bias": 0.5},
        "objects": {"enabled": True},
        "interactions": True,
        "conversations": {"enabled": True, "max_turns": 4},
        "llm": (wc.get("behavior") or {}).get("llm", {}),
    }

    days = args.days if args.days > 0 else None
    store = SnapshotStore()
    runner = ManagedSimulation(wc, nc, seed=args.seed, days=days, store=store)
    server = start_snapshot_server(store, runner, host=args.host, port=args.port)
    sim_thread = runner.run()
    print(f"snapshot server listening on http://{args.host}:{args.port} (seed={args.seed}, days={days})")
    try:
        if days is None:
            while True:
                time.sleep(1.0)
        else:
            sim_thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        runner.stop()
        if sim_thread.is_alive():
            sim_thread.join(timeout=5.0)
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()