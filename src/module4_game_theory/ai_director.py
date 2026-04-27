"""
Adversarial Event Selection

The AI Director uses game theory to select optimal disruptive events.
It analyzes colony state, identifies vulnerabilities, and chooses events
that maximally challenge the player using Minimax, Alpha-Beta, or MCTS.

Game tree:
- Director (max): chooses an event → state after event.
- Player (min): chooses a "response" (e.g. which resource to recover) → state after response.
- Score = challenge(state); Director maximizes, Player minimizes.

Input: Current colony state, available event types
Output: Selected disaster/event specification
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import math
import random
from src.module1_state.colony_state import ColonyState


# Default recovery amount per "player response" in minimax (simplified model)
DEFAULT_PLAYER_RECOVERY = 10.0


@dataclass
class Event:
    """Represents a potential disruptive event."""
    event_type: str  # e.g., "hull_breach", "resource_shortage", "equipment_failure"
    location: str  # e.g., "section_alpha"
    severity: float  # 0.0 to 1.0
    resource_impact: Dict[str, float]  # Changes to resources
    description: str
    # Director "shop" fields (cost-based adversary)
    cost: float = 0.0
    cooldown_turns: int = 0
    tags: Optional[List[str]] = None
    target_station_id: Optional[str] = None
    target_agent_id: Optional[int] = None


class AIDirector:
    """
    AI Director that selects adversarial events using game theory.
    
    The Director acts as the opponent, trying to maximize challenge
    to the player by selecting events that exploit colony weaknesses.
    """
    
    def __init__(self, available_events: List[Event]):
        """
        Initialize AI Director with catalog of available events.
        
        Args:
            available_events: List of possible events the Director can choose
        """
        self.available_events = available_events
        # Tunable behavior knobs (can be set from game settings)
        self.aggression = 1.0
        self.randomness = 0.4
        self.repetition_window = 3
        self.selection_top_k = 4

    def configure(
        self,
        aggression: Optional[float] = None,
        randomness: Optional[float] = None,
        repetition_window: Optional[int] = None,
        selection_top_k: Optional[int] = None,
    ) -> None:
        """Update director behavior settings at runtime."""
        if aggression is not None:
            self.aggression = max(0.1, float(aggression))
        if randomness is not None:
            self.randomness = max(0.0, min(1.0, float(randomness)))
        if repetition_window is not None:
            self.repetition_window = max(1, int(repetition_window))
        if selection_top_k is not None:
            self.selection_top_k = max(1, int(selection_top_k))

    def _resource_stations(self, state: ColonyState) -> List[Dict[str, Any]]:
        """Return normalized station records from infrastructure."""
        stations: List[Dict[str, Any]] = []
        for station_id, info in (state.infrastructure or {}).items():
            if not isinstance(info, dict):
                continue
            if info.get("kind") != "resource_station":
                continue
            center = info.get("center")
            if not isinstance(center, (tuple, list)) or len(center) != 2:
                continue
            stations.append({
                "station_id": station_id,
                "resource_type": info.get("resource_type", ""),
                "center": (int(center[0]), int(center[1])),
                "status": info.get("status", "operational"),
            })
        return stations

    def _get_director_memory(self, state: ColonyState) -> Dict[str, Any]:
        """Get or initialize director memory from infrastructure."""
        infra = state.infrastructure if isinstance(state.infrastructure, dict) else {}
        memory = infra.get("__director_memory__")
        if not isinstance(memory, dict):
            memory = {"recent_events": []}
            infra["__director_memory__"] = memory
            state.infrastructure = infra
        if "recent_events" not in memory or not isinstance(memory["recent_events"], list):
            memory["recent_events"] = []
        return memory

    def _remember_event(self, state: ColonyState, event: Event) -> None:
        """Persist event choice to short-term memory for repetition penalties."""
        memory = self._get_director_memory(state)
        recent = memory.get("recent_events", [])
        target_resource = ""
        if event.resource_impact:
            target_resource = max(event.resource_impact, key=lambda k: abs(event.resource_impact.get(k, 0.0)))
        recent.append({
            "turn": int(getattr(state, "turn_number", 0)),
            "event_type": event.event_type,
            "target_station_id": event.target_station_id or event.location,
            "target_resource": target_resource,
        })
        # Keep a short horizon
        if len(recent) > 8:
            recent = recent[-8:]
        memory["recent_events"] = recent

    def _cooldown_key(self, event: Event) -> str:
        """Key for per-event cooldown tracking in director memory."""
        if event.event_type == "station_breakdown":
            return f"{event.event_type}:{event.target_station_id or event.location}"
        if event.target_agent_id is not None:
            return f"{event.event_type}:agent_{int(event.target_agent_id)}"
        return event.event_type

    def _cooldowns(self, state: ColonyState) -> Dict[str, int]:
        """Get or initialize cooldown map from director memory."""
        memory = self._get_director_memory(state)
        cds = memory.get("cooldowns")
        if not isinstance(cds, dict):
            cds = {}
            memory["cooldowns"] = cds
        # Normalize values to int >= 0
        out: Dict[str, int] = {}
        for k, v in cds.items():
            try:
                out[str(k)] = max(0, int(v))
            except (TypeError, ValueError):
                continue
        memory["cooldowns"] = out
        return out

    def tick_cooldowns(self, state: ColonyState) -> None:
        """Once per turn: decrement cooldown counters."""
        cds = self._cooldowns(state)
        if not cds:
            return
        to_del = []
        for k, v in cds.items():
            nv = max(0, int(v) - 1)
            if nv <= 0:
                to_del.append(k)
            else:
                cds[k] = nv
        for k in to_del:
            cds.pop(k, None)

    def is_on_cooldown(self, state: ColonyState, event: Event) -> bool:
        if int(getattr(event, "cooldown_turns", 0) or 0) <= 0:
            return False
        cds = self._cooldowns(state)
        return self._cooldown_key(event) in cds

    def apply_cooldown(self, state: ColonyState, event: Event) -> None:
        cd = int(getattr(event, "cooldown_turns", 0) or 0)
        if cd <= 0:
            return
        cds = self._cooldowns(state)
        cds[self._cooldown_key(event)] = cd

    def select_event_with_constraints(
        self,
        colony_state: ColonyState,
        *,
        affordable_points: float,
        preferred_event_type: Optional[str] = None,
    ) -> Event:
        """
        Select an event subject to a cost budget and cooldowns.

        Uses the existing weakness-aware scorer, but filters out events that are either
        unaffordable or currently on cooldown.
        """
        candidates = self._targeted_event_candidates(colony_state)
        if not candidates:
            if not self.available_events:
                raise ValueError("No events available")
            return self.available_events[0]

        # Keep only affordable + not on cooldown candidates (optionally matching a preferred type).
        filtered: List[Tuple[Event, float]] = []
        for event, base_score in candidates:
            if preferred_event_type and event.event_type != preferred_event_type:
                continue
            cost = float(getattr(event, "cost", 0.0) or 0.0)
            if cost > float(affordable_points):
                continue
            if self.is_on_cooldown(colony_state, event):
                continue
            filtered.append((event, base_score))

        if not filtered:
            # Nothing affordable or everything cooled down.
            return Event(
                event_type="no_adversarial_event",
                location="n/a",
                severity=0.0,
                resource_impact={},
                description="Director saved points; no affordable disaster this turn.",
                cost=0.0,
            )

        scored: List[Tuple[Event, float]] = []
        for event, base_score in filtered:
            final_score = self._apply_repetition_penalty(colony_state, event, base_score)
            scored.append((event, final_score))

        scored.sort(key=lambda t: t[1], reverse=True)
        top_limit = max(2, min(self.selection_top_k, len(scored)))
        top = scored[:top_limit]
        weights = [max(0.001, s) for _, s in top]
        seed = int(colony_state.world_seed) + int(colony_state.turn_number) * 9973
        rng = random.Random(seed)
        if rng.random() > self.randomness:
            selected = top[0][0]
        else:
            selected = rng.choices([e for e, _ in top], weights=weights, k=1)[0]
        self._remember_event(colony_state, selected)
        self.apply_cooldown(colony_state, selected)
        return selected

    def _isolation_scores(self, state: ColonyState) -> Dict[str, float]:
        """
        Compute per-resource isolation score from station distances.
        Higher means farther from the other station types.
        """
        stations = self._resource_stations(state)
        by_type: Dict[str, Dict[str, Any]] = {}
        for s in stations:
            r = s.get("resource_type")
            if r in ("oxygen", "calories", "integrity"):
                by_type[r] = s
        scores = {"oxygen": 0.0, "calories": 0.0, "integrity": 0.0}
        if len(by_type) < 3:
            return scores
        for r, s in by_type.items():
            sx, sy = s["center"]
            dists: List[float] = []
            for other_r, other in by_type.items():
                if other_r == r:
                    continue
                ox, oy = other["center"]
                dists.append(math.hypot(ox - sx, oy - sy))
            avg = sum(dists) / len(dists) if dists else 0.0
            # Normalize to typical world scale; clamp [0,1]
            scores[r] = max(0.0, min(1.0, avg / 30.0))
        return scores

    def _targeted_event_candidates(self, state: ColonyState) -> List[Tuple[Event, float]]:
        """Build weakness-aware candidate events with base scores."""
        candidates: List[Tuple[Event, float]] = []
        resources = state.resources or {}
        iso = self._isolation_scores(state)
        stations = self._resource_stations(state)
        operational_stations = [s for s in stations if s.get("status") != "failed"]
        living_agents = [a for a in state.agents if a.get("status") != "dead" and a.get("id") is not None]

        # Resource pressure + map isolation
        weakness_by_resource: Dict[str, float] = {}
        for r in ("oxygen", "calories", "integrity"):
            level = float(resources.get(r, 100.0))
            resource_pressure = max(0.0, min(1.0, (100.0 - level) / 100.0))
            weakness_by_resource[r] = 0.65 * resource_pressure + 0.35 * iso.get(r, 0.0)

        # Agent-targeting hazard candidates from catalog templates
        for event in self.available_events:
            if not living_agents:
                break
            target_resource = ""
            if event.resource_impact:
                target_resource = max(event.resource_impact, key=lambda k: abs(event.resource_impact.get(k, 0.0)))
            for agent in living_agents:
                base = 0.1
                agent_pressure = 0.0
                if target_resource:
                    level = float(agent.get(target_resource, 100.0))
                    agent_pressure = max(0.0, min(1.0, (100.0 - level) / 100.0))
                    base += abs(float(event.resource_impact.get(target_resource, 0.0))) * (
                        0.6 * agent_pressure + 0.4 * weakness_by_resource.get(target_resource, 0.0)
                    ) / 40.0
                base *= 1.0 + (event.severity * 0.5)
                agent_event = Event(
                    event_type=event.event_type,
                    location=f"agent_{int(agent.get('id'))}",
                    severity=min(1.0, event.severity + (0.15 * agent_pressure)),
                    resource_impact=dict(event.resource_impact or {}),
                    description=event.description,
                    cost=float(getattr(event, "cost", 0.0) or 0.0),
                    cooldown_turns=int(getattr(event, "cooldown_turns", 0) or 0),
                    tags=list(getattr(event, "tags", None) or []) or None,
                    target_station_id=None,
                    target_agent_id=int(agent.get("id")),
                )
                candidates.append((agent_event, base * self.aggression))

        # Add station_breakdown candidates dynamically for operational stations
        for s in operational_stations:
            r = s.get("resource_type", "")
            score = (0.25 + weakness_by_resource.get(r, 0.0)) * self.aggression
            candidates.append((
                Event(
                    event_type="station_breakdown",
                    location=s.get("station_id", ""),
                    severity=min(1.0, 0.45 + weakness_by_resource.get(r, 0.0) * 0.4),
                    resource_impact={},
                    description=f"{r.capitalize()} station breakdown",
                    target_station_id=s.get("station_id", ""),
                    cost=6.0,
                    cooldown_turns=2,
                    tags=["station", str(r)],
                ),
                score,
            ))

        return candidates

    def _apply_repetition_penalty(self, state: ColonyState, event: Event, score: float) -> float:
        """Penalize recently repeated event types/targets/resources."""
        memory = self._get_director_memory(state)
        recent = list(memory.get("recent_events", []))
        if not recent:
            return score

        turn = int(getattr(state, "turn_number", 0))
        target_station = event.target_station_id or event.location
        target_resource = ""
        if event.resource_impact:
            target_resource = max(event.resource_impact, key=lambda k: abs(event.resource_impact.get(k, 0.0)))

        penalty = 0.0
        for entry in recent[-self.repetition_window:]:
            age = max(1, turn - int(entry.get("turn", turn)))
            decay = 1.0 / age
            if entry.get("event_type") == event.event_type:
                penalty += 0.35 * decay
            if target_station and entry.get("target_station_id") == target_station:
                penalty += 0.45 * decay
            if target_resource and entry.get("target_resource") == target_resource:
                penalty += 0.3 * decay
        return max(0.01, score - penalty)

    def _select_event_targeted(self, colony_state: ColonyState) -> Event:
        """
        Select event using weakness-aware scoring with anti-repetition memory
        and weighted randomness for semi-random player-facing behavior.
        """
        candidates = self._targeted_event_candidates(colony_state)
        if not candidates:
            # Fallback to catalog if something went wrong
            if not self.available_events:
                raise ValueError("No events available")
            event = self.available_events[0]
            self._remember_event(colony_state, event)
            return event

        # Hard anti-repeat rule: if any of the previous 5 events was station_breakdown,
        # block station_breakdown from this selection.
        memory = self._get_director_memory(colony_state)
        recent = list(memory.get("recent_events", []))
        station_breakdown_recent = any(
            entry.get("event_type") == "station_breakdown" for entry in recent[-5:]
        )
        filtered_candidates = [
            (event, base_score)
            for event, base_score in candidates
            if not (station_breakdown_recent and event.event_type == "station_breakdown")
        ]
        if not filtered_candidates:
            filtered_candidates = candidates

        scored: List[Tuple[Event, float]] = []
        for event, base_score in filtered_candidates:
            final_score = self._apply_repetition_penalty(colony_state, event, base_score)
            scored.append((event, final_score))

        # Focus on top-k while preserving semi-random feel.
        scored.sort(key=lambda t: t[1], reverse=True)
        top_limit = max(2, min(self.selection_top_k, len(scored)))
        top = scored[:top_limit]
        weights = [max(0.001, s) for _, s in top]
        seed = int(colony_state.world_seed) + int(colony_state.turn_number) * 9973
        rng = random.Random(seed)
        # Lower randomness favors best-scoring deterministic choice.
        if rng.random() > self.randomness:
            selected = top[0][0]
        else:
            selected = rng.choices([e for e, _ in top], weights=weights, k=1)[0]
        self._remember_event(colony_state, selected)
        return selected
    
    def select_event_minimax(self, colony_state: ColonyState, depth: int = 3) -> Event:
        """
        Select event using Minimax algorithm.

        Assumes optimal play: Director maximizes challenge, Player minimizes it
        (we model Player as choosing the best single-resource recovery each "turn").
        Picks the event that has the highest minimax value (best for Director
        after Player's best response).

        Args:
            colony_state: Current colony state
            depth: Number of full plies (Director + Player pairs). 1 = one event then one response.

        Returns:
            Selected event
        """
        # Keep API name for compatibility, but use the newer targeted selector
        # that models map weaknesses and anti-repetition behavior.
        return self._select_event_targeted(colony_state)

    def _get_state_challenge(self, state: ColonyState) -> float:
        """
        Score how challenging/vulnerable a state is (for the player).
        Higher = more challenging = better for the Director.
        """
        score = 0.0
        for resource, level in state.resources.items():
            # Low resources = high challenge
            score += (100.0 - max(0.0, min(100.0, level))) / 100.0
        # Few agents = more vulnerability
        agent_factor = max(0.0, 1.0 - len(state.agents) / 5.0)
        score += agent_factor
        return score

    def _simulate_event(self, state: ColonyState, event: Event) -> ColonyState:
        """
        Return a copy of state with the event's resource impact applied.
        Does not mutate the original state.
        """
        copy = state.copy()
        copy.consume_resources(event.resource_impact)
        return copy

    def _get_player_responses(self, state: ColonyState) -> List[Dict[str, Any]]:
        """
        Simple model of player responses: choose one resource to recover by a fixed amount.
        Returns a list of {"resource": name, "delta": amount} (positive = recovery).
        """
        responses: List[Dict[str, Any]] = [{}]  # do nothing
        for resource in state.resources:
            responses.append({"resource": resource, "delta": DEFAULT_PLAYER_RECOVERY})
        return responses

    def _simulate_player_response(
        self, state: ColonyState, response: Dict[str, Any]
    ) -> ColonyState:
        """Return a copy of state with the player response applied."""
        copy = state.copy()
        if response:
            copy.consume_resources(
                {response["resource"]: response["delta"]}
            )  # consume_resources adds the delta (positive = gain)
        return copy

    def _minimax_max(self, state: ColonyState, depth: int) -> float:
        """Director's turn: maximize challenge over events."""
        if depth <= 0:
            return self._get_state_challenge(state)
        best = float("-inf")
        for event in self.available_events:
            child = self._simulate_event(state, event)
            value = self._minimax_min(child, depth - 1)
            best = max(best, value)
        return best

    def _minimax_min(self, state: ColonyState, depth: int) -> float:
        """Player's turn: minimize challenge over (simplified) responses."""
        if depth <= 0:
            return self._get_state_challenge(state)
        best = float("inf")
        for response in self._get_player_responses(state):
            child = self._simulate_player_response(state, response)
            value = self._minimax_max(child, depth - 1)
            best = min(best, value)
        return best
    
    def select_event_alphabeta(self, colony_state: ColonyState, depth: int = 3) -> Event:
        """
        Select event using Alpha-Beta Pruning.
        
        Alpha-Beta is an optimized version of Minimax that prunes
        branches that cannot affect the final decision.
        
        Args:
            colony_state: Current colony state
            depth: How many turns ahead to look
            
        Returns:
            Selected event
        """
        # TODO: Implement Alpha-Beta Pruning
        # 1. Same as Minimax but with alpha-beta bounds
        # 2. Prune branches where alpha >= beta
        # 3. More efficient than pure Minimax
        
        return self.select_event_minimax(colony_state, depth)  # Placeholder
    
    def select_event_mcts(self, colony_state: ColonyState, iterations: int = 1000) -> Event:
        """
        Select event using Monte Carlo Tree Search (MCTS).
        
        MCTS uses random simulations to evaluate event choices,
        building a search tree through repeated playouts.
        
        Args:
            colony_state: Current colony state
            iterations: Number of MCTS iterations to run
            
        Returns:
            Selected event
        """
        # TODO: Implement MCTS
        # 1. Build search tree by selecting, expanding, simulating, backpropagating
        # 2. Use UCB1 formula for node selection
        # 3. Run random simulations to evaluate nodes
        # 4. Choose event from most visited/valuable node
        
        return self._select_by_weakness(colony_state)  # Placeholder
    
    def _evaluate_challenge(self, colony_state: ColonyState, event: Event) -> float:
        """
        Evaluate how challenging an event would be to the colony.
        
        Higher score = more challenging = better for AI Director.
        
        Args:
            colony_state: Current state
            event: Event to evaluate
            
        Returns:
            Challenge score (higher = more challenging)
        """
        # TODO: Implement challenge evaluation
        # Consider:
        # - Which resources are already low (target those)
        # - Event severity
        # - Location importance
        # - Cascading effects
        
        score = 0.0
        for resource, impact in event.resource_impact.items():
            current_level = colony_state.resources.get(resource, 100.0)
            # More challenging if resource is already low
            score += abs(impact) * (1.0 - current_level / 100.0)
        
        score *= event.severity
        return score
    
    def _select_by_weakness(self, colony_state: ColonyState) -> Event:
        """
        Simple heuristic: select event that targets weakest resource.
        
        Args:
            colony_state: Current state
            
        Returns:
            Event targeting weakest resource
        """
        # Find weakest resource
        weakest_resource = min(
            colony_state.resources.items(),
            key=lambda x: x[1]
        )[0]
        
        # Find event that most impacts weakest resource
        best_event = self.available_events[0]
        best_impact = 0.0
        
        for event in self.available_events:
            impact = abs(event.resource_impact.get(weakest_resource, 0.0))
            if impact > best_impact:
                best_impact = impact
                best_event = event
        
        return best_event
    
    def identify_vulnerabilities(self, colony_state: ColonyState) -> List[str]:
        """
        Identify colony vulnerabilities that events can exploit.
        
        Args:
            colony_state: Current state
            
        Returns:
            List of human-readable vulnerability descriptions
        """

        vulnerabilities: List[str] = []

        resources = colony_state.resources
        agents = colony_state.agents
        living_agents = [a for a in agents if a.get("status") != "dead"]

        # --- Global resource levels ---
        low_resources: List[str] = []
        critical_resources: List[str] = []
        for resource, level in resources.items():
            if level < 20.0:
                critical_resources.append(resource)
                vulnerabilities.append(f"CRITICAL {resource} level: {level:.1f}%")
            elif level < 40.0:
                low_resources.append(resource)
                vulnerabilities.append(f"Low {resource} reserve: {level:.1f}%")

        if len(critical_resources) >= 2:
            vulnerabilities.append(
                f"Multiple resources in critical range: {', '.join(sorted(critical_resources))}"
            )
        elif len(low_resources) + len(critical_resources) >= 2:
            vulnerabilities.append(
                f"Several resources are low: {', '.join(sorted(low_resources + critical_resources))}"
            )

        # --- Agent count and status ---
        if len(living_agents) == 0 and agents:
            vulnerabilities.append("All agents are dead – colony cannot respond to events.")
        elif len(living_agents) < 2:
            vulnerabilities.append(
                f"Very few active agents ({len(living_agents)}); colony is fragile to any disruption."
            )
        elif len(living_agents) < 4:
            vulnerabilities.append(
                f"Low active agent count ({len(living_agents)}); limited capacity to recover from events."
            )

        dead_count = sum(1 for a in agents if a.get("status") == "dead")
        if dead_count > 0:
            vulnerabilities.append(f"{dead_count} agent(s) already dead – reduced redundancy.")

        # --- Per-agent resource health ---
        for agent in living_agents:
            name = agent.get("name", f"Agent {agent.get('id')}")
            for res_name in ("oxygen", "calories", "integrity"):
                value = agent.get(res_name, 100.0)
                if value < 20.0:
                    vulnerabilities.append(
                        f"{name} has critically low {res_name} ({value:.1f}%)"
                    )
                elif value < 40.0:
                    vulnerabilities.append(
                        f"{name} has low {res_name} ({value:.1f}%)"
                    )

        # --- Distance / positioning heuristics ---
        # We don't know exact station locations in this module, but we can approximate:
        # - (0, 0) acts as a "core" / hub location
        # - Large distances from the core mean slower access to any centralized resource
        if living_agents:
            distances = []
            for a in living_agents:
                loc = a.get("location")
                if isinstance(loc, (tuple, list)) and len(loc) == 2:
                    x, y = float(loc[0]), float(loc[1])
                    # Use Manhattan distance from origin as a simple proxy
                    distances.append(abs(x) + abs(y))
            if distances:
                avg_dist = sum(distances) / len(distances)
                max_dist = max(distances)
                if avg_dist > 20.0:
                    vulnerabilities.append(
                        f"Agents are on average far from the core (avg distance {avg_dist:.1f}); slow access to resources."
                    )
                if max_dist > 30.0:
                    vulnerabilities.append(
                        f"Some agents are extremely isolated from the core (max distance {max_dist:.1f})."
                    )

        # --- Infrastructure / redundancy ---
        infra = colony_state.infrastructure or {}
        if not infra:
            vulnerabilities.append("No infrastructure locations defined; no explicit redundancy for life-support systems.")
        else:
            failed = []
            damaged = []
            for name, info in infra.items():
                status = (info or {}).get("status", "")
                integrity = (info or {}).get("integrity", 100.0)
                if status == "failed" or integrity <= 0:
                    failed.append(name)
                elif status == "damaged" or integrity < 50.0:
                    damaged.append(name)

            if failed:
                vulnerabilities.append(
                    f"Infrastructure failed at: {', '.join(sorted(failed))}"
                )
            if damaged and not failed:
                vulnerabilities.append(
                    f"Infrastructure damaged at: {', '.join(sorted(damaged))}"
                )

        return vulnerabilities
