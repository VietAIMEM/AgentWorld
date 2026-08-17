# NPC WORLD SIMULATION — v0.1

Build a clean, modular, extensible **NPC world simulation** in Python.

## 1. Goal

Create a simulation where NPCs can independently:

* perceive the world
* have needs
* choose goals
* choose actions
* execute actions
* remember important events
* interact with resources and locations
* change their state over time

The simulation must run **without player control**.

For this version, NPC decision-making must use **deterministic/rule-based logic only**.

Do NOT use LLMs, neural networks, reinforcement learning, or external AI APIs.

The architecture must make it easy to replace the decision system later with:

* Utility AI
* GOAP
* behavior trees
* LLM-based reasoning

without rewriting the rest of the simulation.

---

# 2. Technology

Use:

* Python 3.11+
* Standard library first
* dataclasses
* type hints
* enums
* random
* JSON

Avoid unnecessary dependencies.

The simulation must run from:

```bash
python main.py
```

No GUI is required.

The first version should be a terminal-based simulation.

---

# 3. Core Architecture

Use this architecture:

```text
World
  │
  ├── Time
  ├── Locations
  ├── Resources
  ├── NPCs
  └── Events
        │
        ▼
      NPC
        │
        ├── Perception
        ├── Needs
        ├── Memory
        ├── Personality
        ├── Goals
        ├── Decision System
        └── Actions
```

Separate **simulation state** from **decision logic**.

An NPC must NOT directly manipulate the entire World.

Use clear interfaces between systems.

---

# 4. Project Structure

Create:

```text
world_sim/
│
├── main.py
│
├── simulation/
│   ├── __init__.py
│   ├── simulation.py
│   ├── world.py
│   ├── clock.py
│   └── events.py
│
├── npc/
│   ├── __init__.py
│   ├── npc.py
│   ├── needs.py
│   ├── memory.py
│   ├── personality.py
│   ├── goals.py
│   └── perception.py
│
├── decision/
│   ├── __init__.py
│   ├── decision_system.py
│   └── rule_based.py
│
├── actions/
│   ├── __init__.py
│   ├── action.py
│   ├── movement.py
│   ├── eating.py
│   ├── sleeping.py
│   ├── working.py
│   └── social.py
│
├── world/
│   ├── __init__.py
│   ├── location.py
│   ├── resource.py
│   └── economy.py
│
├── config/
│   ├── world.json
│   └── npcs.json
│
└── tests/
    ├── test_npc.py
    ├── test_needs.py
    ├── test_decision.py
    └── test_simulation.py
```

Keep modules small.

Do not create one giant file.

---

# 5. Simulation Clock

The world operates using discrete ticks.

Example:

```text
1 tick = 10 minutes
```

The clock should contain:

```text
day
hour
minute
tick
```

Example:

```text
Day 1 06:00
Day 1 06:10
Day 1 06:20
...
```

Allow the tick duration to be configured.

---

# 6. World

Create a `World` object containing:

```text
time
locations
resources
npcs
events
```

Example locations:

```text
Home
Farm
Market
Forest
Tavern
```

Locations should have:

* id
* name
* type
* connected locations
* available resources
* available activities

Example:

```text
Home <-> Market
Market <-> Farm
Market <-> Tavern
Farm <-> Forest
```

NPCs should be able to move only between connected locations.

---

# 7. NPC

Create an NPC model containing:

```text
id
name
age
money
location
needs
personality
memory
goals
current_action
```

Do NOT put decision-making directly inside the NPC class.

The NPC should expose state and capabilities.

The decision system decides what the NPC should do.

---

# 8. Needs

Implement:

```text
Hunger
Energy
Health
Social
Money
```

Use values:

```text
0.0 → 100.0
```

Interpretation:

```text
Hunger:
0   = not hungry
100 = extremely hungry

Energy:
0   = exhausted
100 = fully rested
```

Needs must change automatically with time.

Example:

```text
Hunger increases every tick.

Energy decreases while working.

Energy increases while sleeping.
```

Keep the rates configurable.

Do not hardcode values throughout the code.

---

# 9. Personality

Create simple personality traits:

```text
sociability
ambition
risk_tolerance
work_ethic
generosity
```

Range:

```text
0.0 → 1.0
```

Personality should influence decisions.

For example:

```text
High ambition
→ prefers working

High sociability
→ prefers social activities

High risk tolerance
→ more willing to perform risky actions
```

Do not make personality directly execute actions.

Personality should only influence decision scoring.

---

# 10. Memory

Create a simple memory system.

NPCs should be able to remember events such as:

```text
met_npc
worked
ate
received_money
lost_money
bought_food
sold_food
visited_location
```

Each memory should contain:

```text
timestamp
event_type
description
importance
related_entity
```

Implement a maximum memory size.

Old low-importance memories can be removed.

Do not implement sophisticated AI memory yet.

---

# 11. Perception

The NPC should not automatically know everything in the world.

Create a `PerceptionSystem`.

The NPC should perceive:

* current location
* nearby NPCs
* available resources
* available activities
* relevant world events

For example:

```text
NPC at Market

Perception:
- Bob is here
- Food is available
- Shop is open
- Farm is connected
```

The decision system must use perceived information rather than directly querying arbitrary world state.

---

# 12. Goals

Create goals such as:

```text
Eat
Sleep
Work
EarnMoney
Socialize
Explore
Rest
```

A goal should contain:

```text
type
priority
target
status
```

Goals should be generated from the NPC's current state.

Example:

```text
Hunger > 80
→ Eat becomes high priority

Energy < 20
→ Sleep becomes high priority

Money < 10
→ EarnMoney becomes higher priority
```

---

# 13. Decision System

Create an abstract interface:

```python
class DecisionSystem:
    def decide(self, npc, perception, world):
        ...
```

Then implement:

```text
RuleBasedDecisionSystem
```

The NPC must use the decision system through this interface.

This is extremely important because later we should be able to add:

```text
UtilityDecisionSystem
GOAPDecisionSystem
LLMDecisionSystem
```

without changing the NPC.

---

# 14. Rule-Based Decision Logic

Implement priority-based rules.

Example:

```text
IF health is critical
    → seek safety

ELSE IF hunger > 80
    → find food

ELSE IF energy < 20
    → go home and sleep

ELSE IF money < 20
    → find work

ELSE IF social < 20
    → socialize

ELSE
    → continue normal activity
```

However, do NOT hardcode this entire logic inside one giant `if/elif`.

Create individual rules.

Example:

```text
LowHealthRule
HighHungerRule
LowEnergyRule
LowMoneyRule
LowSocialRule
DefaultActivityRule
```

Each rule should be independently testable.

The decision system evaluates the rules and selects the highest-priority valid decision.

---

# 15. Actions

Create an abstract action:

```python
class Action:
    def can_execute(self, npc, world):
        ...

    def start(self, npc, world):
        ...

    def update(self, npc, world):
        ...

    def is_complete(self, npc, world):
        ...

    def cancel(self, npc, world):
        ...
```

Implement:

```text
MoveAction
EatAction
SleepAction
WorkAction
SocializeAction
RestAction
ExploreAction
```

Actions should take time.

Do NOT make every action happen instantly.

Example:

```text
Move:
10–30 minutes

Eat:
10 minutes

Sleep:
several hours

Work:
several hours
```

---

# 16. Movement

NPCs should have:

```text
current_location
target_location
```

Movement should follow the world's connected locations.

For v0.1, simple graph traversal is enough.

Do not implement advanced pathfinding yet.

---

# 17. Jobs

Create basic jobs:

```text
Farmer
Merchant
Worker
```

A job should define:

```text
name
work_location
income_per_tick
energy_cost
```

Example:

```text
Farmer
location = Farm
income = 2
energy_cost = 1
```

NPCs can work according to their job.

---

# 18. Economy

Implement a very simple economy.

NPCs have money.

Actions can change money:

```text
Work
→ money increases

Buy food
→ money decreases

Sell resource
→ money increases
```

Create an `EconomySystem`.

Do not build a complex market simulation yet.

---

# 19. Food

Create a simple food resource.

Example:

```text
Food
price = 5
hunger_restore = 40
```

NPC can:

```text
Go to Market
→ Buy Food
→ Eat Food
→ Hunger decreases
→ Money decreases
```

---

# 20. Social Interaction

Implement basic NPC interaction.

If two NPCs are at the same location:

```text
NPC A can talk to NPC B
```

Talking should:

```text
increase social need
create memory
increase relationship score
```

Create a simple relationship system:

```text
relationship[A][B] = -100 → 100
```

For v0.1:

```text
talking
→ relationship +1
```

Do not implement complex dialogue yet.

---

# 21. Daily Schedule

NPCs should have a basic schedule, but the schedule must NOT completely control them.

Example:

```text
06:00 → wake up
08:00 → work
12:00 → eat
13:00 → work
17:00 → finish work
18:00 → socialize
22:00 → sleep
```

Needs and emergencies should override the schedule.

Example:

```text
Normally:
Work

But:

Hunger = 95
→ Stop working
→ Find food
```

This is important for creating autonomous behavior.

---

# 22. Simulation Loop

Implement:

```text
while simulation_running:

    world.update_time()

    for npc in world.npcs:

        perception = perceive_world(npc, world)

        update_needs(npc)

        update_memory(npc)

        goal = decision_system.decide(
            npc,
            perception,
            world
        )

        action = action_manager.update(
            npc,
            goal,
            world
        )

    world.process_events()

    display_state()
```

Make sure the order is logically consistent.

An NPC should not make a decision using stale state.

---

# 23. Action Persistence

Do NOT make NPCs reconsider their decision every tick.

For example:

```text
NPC decides:

Work for 4 hours
```

The NPC should continue working until:

```text
work completed
OR
important need appears
OR
action becomes impossible
```

Use an action interruption system.

Example:

```text
Current action:
Work

Hunger reaches 90

→ interrupt Work
→ choose Eat
```

---

# 24. Determinism

The simulation should support a random seed.

Example:

```python
Simulation(seed=42)
```

Running the same simulation with the same seed should produce the same result.

This is important for debugging.

---

# 25. Configuration

Do not hardcode NPC data.

Use:

```text
config/npcs.json
```

Example:

```json
{
    "npcs": [
        {
            "id": "npc_001",
            "name": "Alice",
            "money": 50,
            "job": "farmer",
            "personality": {
                "sociability": 0.7,
                "ambition": 0.8,
                "risk_tolerance": 0.3,
                "work_ethic": 0.9,
                "generosity": 0.5
            }
        }
    ]
}
```

World configuration should also be stored separately.

---

# 26. Logging

The simulation must produce readable logs.

Example:

```text
[Day 1 06:00] Alice woke up at Home.
[Day 1 07:10] Alice decided to go to Farm.
[Day 1 07:30] Alice started working.
[Day 1 10:30] Alice earned $12.
[Day 1 12:00] Alice became hungry.
[Day 1 12:10] Alice went to Market.
[Day 1 12:30] Alice bought food.
[Day 1 12:40] Alice ate food.
```

Support log levels:

```text
INFO
DEBUG
EVENT
```

Allow verbose logging to be turned on/off.

---

# 27. Simulation Statistics

At the end of the simulation show:

```text
Simulation completed.

Days simulated: 30
NPCs: 20

Total money:
Average hunger:
Average energy:

Jobs:
Farmer: 7
Merchant: 4
Worker: 9

Deaths: 0
Food consumed: 183
Work actions: 521
Social interactions: 204
```

Also show individual NPC state.

---

# 28. Testing

Write tests for:

```text
Needs
Memory
Personality
Perception
Decision rules
Actions
Movement
Economy
NPC behavior
Simulation
```

Example:

```text
Given hunger > 80
When NPC makes a decision
Then Eat should have higher priority.
```

Example:

```text
Given energy < 20
When NPC makes a decision
Then Sleep should be selected.
```

---

# 29. Design Requirements

Follow these rules strictly:

1. Keep responsibilities separated.
2. Avoid giant classes.
3. Avoid giant functions.
4. Avoid global mutable state.
5. Use dependency injection where practical.
6. Use type hints.
7. Use enums for fixed states.
8. Keep configuration separate from logic.
9. Keep decision-making separate from actions.
10. Keep NPC state separate from World state.
11. Make every major system independently testable.
12. Prefer composition over inheritance.
13. Do not over-engineer v0.1.
14. Do not add a GUI.
15. Do not use an LLM.
16. Do not use machine learning.
17. Do not implement advanced pathfinding.
18. Do not implement complex economics.
19. Do not implement complex dialogue.

---

# 30. Future-Proof Architecture

The most important requirement is that the following architecture remains possible later:

```text
                DecisionSystem
                     │
        ┌────────────┼────────────┐
        ↓            ↓            ↓
   RuleBased      Utility AI      GOAP
                                  │
                                  ↓
                                 LLM
```

The rest of the simulation should not care which decision system is being used.

For example:

```python
simulation = Simulation(
    decision_system=RuleBasedDecisionSystem()
)
```

Later:

```python
simulation = Simulation(
    decision_system=UtilityDecisionSystem()
)
```

And eventually:

```python
simulation = Simulation(
    decision_system=LLMDecisionSystem()
)
```

without rewriting:

```text
NPC
World
Needs
Memory
Actions
Economy
Simulation
```

---

# 31. Initial Demo

Create a working demo with:

```text
20 NPCs
5 locations
3 jobs
food
money
sleep
work
movement
social interaction
memory
personality
needs
rule-based decisions
```

Run the simulation for:

```text
30 days
```

with:

```text
1 tick = 10 minutes
```

The simulation should run automatically without user interaction.

At the end, print:

```text
WORLD SUMMARY

Days:
Population:
Money:
Food:

NPC SUMMARY

Name
Age
Job
Money
Location
Hunger
Energy
Social
Current Goal
Current Action
```

---

# 32. Implementation Order

Build the system in this order:

### Phase 1

```text
World
Clock
Location
NPC
Simulation loop
```

### Phase 2

```text
Needs
Actions
Movement
Sleep
Food
```

### Phase 3

```text
Jobs
Money
Economy
```

### Phase 4

```text
Personality
Goals
Decision System
Rules
```

### Phase 5

```text
Memory
Perception
Social interaction
Relationships
```

### Phase 6

```text
Schedules
Events
Statistics
Testing
```

Do not skip ahead.

After each phase, make sure the simulation is runnable.

---

# 33. First Milestone

The first milestone is NOT to create an advanced AI.

The first milestone is:

```text
20 NPCs
      ↓
Live in a world
      ↓
Have needs
      ↓
Choose actions
      ↓
Move
      ↓
Work
      ↓
Earn money
      ↓
Buy food
      ↓
Eat
      ↓
Sleep
      ↓
Interact
      ↓
Repeat
```

The world must continue running even if there is no player.

The final result should feel like a **small autonomous society simulation**, not a traditional game.

---

# 34. Coding Instructions

Before writing code:

1. Analyze the architecture.
2. Explain the responsibility of each module briefly.
3. Identify dependencies between modules.
4. Then implement Phase 1.
5. Run/test Phase 1.
6. Fix errors.
7. Continue to Phase 2.
8. Do not dump the entire project without testing.

When adding a new system, keep the existing architecture intact.

Always prioritize:

```text
Correctness
>
Maintainability
>
Extensibility
>
Performance
>
Complexity
```

Do not add features that are not required for the current phase.
