"""
Rule Enforcement Engine

This module uses propositional logic to check survival constraints
and enforce game rules. It evaluates colony state and identifies
violations that trigger consequences (e.g., agent death).

Input: Current colony state
Output: Constraint violation report with consequences
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from src.module1_state.colony_state import ColonyState


@dataclass
class Violation:
    """Represents a rule violation and its consequence."""
    agent_id: Optional[int]  # None if violation affects entire colony
    violation_type: str  # e.g., "oxygen_zero", "calories_zero", "integrity_zero"
    consequence: str  # e.g., "death", "incapacitation", "system_failure"
    applied: bool  # Whether the consequence has been applied
    description: str  # Human-readable description


class RuleEngine:
    """
    Enforces survival rules using propositional logic.
    
    Rules are encoded as logical constraints:
    - "If oxygen = 0 then agent dies"
    - "If calories = 0 then agent becomes incapacitated"
    - "If integrity = 0 then system failure"
    
    Uses logical entailment to check if current state violates rules.
    """
    
    def __init__(self):
        """Initialize rule engine with survival rules."""
        self.rules = self._initialize_rules()
    
    def _initialize_rules(self) -> List[Dict[str, Any]]:
        """
        Define survival rules as logical constraints.
        
        Returns:
            List of rule definitions
        """
        return [
            {
                "name": "oxygen_zero_death",
                "condition": lambda state, agent: agent.get("oxygen", 0) <= 0,
                "consequence": "death",
                "scope": "agent"
            },
            {
                "name": "calories_zero_incapacitation",
                "condition": lambda state, agent: agent.get("calories", 0) <= 0,
                "consequence": "incapacitation",
                "scope": "agent"
            },
            {
                "name": "integrity_zero_system_failure",
                "condition": lambda state, agent: state.resources.get("integrity", 0) <= 0,
                "consequence": "system_failure",
                "scope": "colony"
            },
            # Add more rules as needed
        ]
    
    def check_violations(self, colony_state: ColonyState) -> List[Violation]:
        """
        Check colony state against all rules and return violations.
        
        This is called during the Logic phase before other phases
        to identify rule violations that need to be applied.
        
        Args:
            colony_state: Current state to check
            
        Returns:
            List of violations found
        """
        violations = []
        
        # Check agent-level rules
        for i, agent in enumerate(colony_state.agents):
            for rule in self.rules:
                if rule["scope"] == "agent":
                    if rule["condition"](colony_state, agent):
                        violations.append(Violation(
                            agent_id=i,
                            violation_type=rule["name"],
                            consequence=rule["consequence"],
                            applied=False,
                            description=f"Agent {i}: {rule['name']}"
                        ))
        
        # Check colony-level rules
        for rule in self.rules:
            if rule["scope"] == "colony":
                if rule["condition"](colony_state, None):
                    violations.append(Violation(
                        agent_id=None,
                        violation_type=rule["name"],
                        consequence=rule["consequence"],
                        applied=False,
                        description=f"Colony: {rule['name']}"
                    ))
        
        return violations
    
    def apply_violations(self, colony_state: ColonyState, violations: List[Violation]) -> None:
        """
        Apply consequences of violations to colony state.
        
        Args:
            colony_state: State to modify
            violations: List of violations to apply
        """
        for violation in violations:
            if violation.applied:
                continue
            
            if violation.consequence == "death" and violation.agent_id is not None:
                # Remove agent from colony
                colony_state.remove_agent(violation.agent_id)
                violation.applied = True
            
            elif violation.consequence == "incapacitation" and violation.agent_id is not None:
                # Mark agent as incapacitated
                colony_state.update_agent(violation.agent_id, {"status": "incapacitated"})
                violation.applied = True
            
            elif violation.consequence == "system_failure":
                # Apply system-wide failure
                colony_state.resources["integrity"] = 0
                violation.applied = True
    
    def evaluate_state(self, colony_state: ColonyState) -> Dict[str, Any]:
        """
        Complete evaluation: check violations and apply consequences.
        
        This is the main entry point for the Logic phase.
        
        Args:
            colony_state: State to evaluate
            
        Returns:
            Report dictionary with violations and actions taken
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
                    "description": v.description
                }
                for v in violations
            ],
            "state_after": colony_state.to_dict()
        }
