"""
Rule Enforcement Engine

Uses propositional logic to check survival constraints and enforce game rules.
Rules are implications: "If condition P then consequence Q" (e.g., "If oxygen ≤ 0
then agent dies"). The engine evaluates the colony state, finds violations, and
applies consequences.

Input:  Current colony state (Module 1)
Output: Constraint violation report with consequences
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from src.module1_state.colony_state import ColonyState


# Consequence types (used when applying violations)
CONSEQUENCE_DEATH = "death"
CONSEQUENCE_INCAPACITATION = "incapacitation"
CONSEQUENCE_SYSTEM_FAILURE = "system_failure"

# Rule scope
SCOPE_AGENT = "agent"
SCOPE_COLONY = "colony"


@dataclass
class Violation:
    """
    A single rule violation and its consequence.

    agent_id: For agent-scoped rules, the index of the agent in colony_state.agents.
              For colony-scoped rules, None.
    """

    agent_id: Optional[int]
    violation_type: str
    consequence: str
    applied: bool
    description: str


class RuleEngine:
    """
    Enforces survival rules using propositional logic.

    Each rule is an implication: if condition(state, agent) holds, then the
    consequence is applied. Agent-level rules are checked per agent; colony-level
    rules are checked once per state.
    """

    def __init__(self) -> None:
        self.rules = self._build_rules()

    def _build_rules(self) -> List[Dict[str, Any]]:
        """Build the list of survival rules (condition + consequence + scope)."""
        return [
            {
                "name": "oxygen_zero_death",
                "condition": self._agent_oxygen_zero,
                "consequence": CONSEQUENCE_DEATH,
                "scope": SCOPE_AGENT,
            },
            {
                "name": "calories_zero_incapacitation",
                "condition": self._agent_calories_zero,
                "consequence": CONSEQUENCE_INCAPACITATION,
                "scope": SCOPE_AGENT,
            },
            {
                "name": "integrity_zero_system_failure",
                "condition": self._colony_integrity_zero,
                "consequence": CONSEQUENCE_SYSTEM_FAILURE,
                "scope": SCOPE_COLONY,
            },
        ]

    # --- Condition predicates (propositional logic: "P" in "if P then Q") ---

    def _agent_oxygen_zero(self, state: ColonyState, agent: Dict[str, Any]) -> bool:
        """True if this agent's oxygen is zero or below."""
        return agent.get("oxygen", 0) <= 0

    def _agent_calories_zero(self, state: ColonyState, agent: Dict[str, Any]) -> bool:
        """True if this agent's calories are zero or below."""
        return agent.get("calories", 0) <= 0

    def _colony_integrity_zero(self, state: ColonyState, agent: Optional[Dict[str, Any]]) -> bool:
        """True if colony-wide integrity is zero or below. (agent argument unused.)"""
        return state.resources.get("integrity", 0) <= 0

    # --- Public API ---

    def check_violations(self, colony_state: ColonyState) -> List[Violation]:
        """
        Check the colony state against all rules. Does not modify state.

        Returns a list of violations; each violation can later be applied
        via apply_violations.
        """
        violations: List[Violation] = []

        for rule in self.rules:
            if rule["scope"] == SCOPE_AGENT:
                for index, agent in enumerate(colony_state.agents):
                    if rule["condition"](colony_state, agent):
                        violations.append(
                            Violation(
                                agent_id=index,
                                violation_type=rule["name"],
                                consequence=rule["consequence"],
                                applied=False,
                                description=f"Agent {index}: {rule['name']}",
                            )
                        )
            else:
                if rule["condition"](colony_state, None):
                    violations.append(
                        Violation(
                            agent_id=None,
                            violation_type=rule["name"],
                            consequence=rule["consequence"],
                            applied=False,
                            description=f"Colony: {rule['name']}",
                        )
                    )

        return violations

    def apply_violations(
        self, colony_state: ColonyState, violations: List[Violation]
    ) -> None:
        """
        Apply the consequences of each violation to the colony state.

        Deaths are applied in reverse index order so that removing one agent
        does not invalidate the indices of other violations.
        """
        # Apply non-death consequences first (they don't change list indices)
        for v in violations:
            if v.applied:
                continue
            if v.consequence == CONSEQUENCE_INCAPACITATION and v.agent_id is not None:
                colony_state.update_agent(v.agent_id, {"status": "incapacitated"}, validate=False)
                v.applied = True
            elif v.consequence == CONSEQUENCE_SYSTEM_FAILURE:
                colony_state.resources["integrity"] = 0
                v.applied = True

        # Apply deaths in reverse index order so indices remain valid
        death_violations = [v for v in violations if v.consequence == CONSEQUENCE_DEATH and v.agent_id is not None]
        for v in sorted(death_violations, key=lambda x: x.agent_id, reverse=True):
            if v.applied:
                continue
            colony_state.remove_agent(v.agent_id)
            v.applied = True

    def evaluate_state(self, colony_state: ColonyState) -> Dict[str, Any]:
        """
        Run the Logic phase: check all rules, apply consequences, return a report.

        This is the main entry point for the game engine's Logic phase.
        """
        violations = self.check_violations(colony_state)
        self.apply_violations(colony_state, violations)

        return {
            "violations_found": len(violations),
            "violations": [
                {
                    "agent_id": v.agent_id,
                    "type": v.violation_type,
                    "consequence": v.consequence,
                    "description": v.description,
                }
                for v in violations
            ],
            "state_after": colony_state.to_dict(),
        }
