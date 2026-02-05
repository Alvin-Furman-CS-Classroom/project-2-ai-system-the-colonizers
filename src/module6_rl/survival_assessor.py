"""
Survival Assessment & Adaptation

This module evaluates colony survival probability and provides
risk assessment. Can use Reinforcement Learning (Q-Learning) or
heuristic evaluation.

Input: Current colony state, historical gameplay data (optional)
Output: Survival probability score, risk assessment report
"""

from typing import Dict, Any, Optional, List
from src.module1_state.colony_state import ColonyState


class SurvivalAssessor:
    """
    Assesses colony survival probability and identifies risks.
    
    Can use:
    - Reinforcement Learning (Q-Learning) to learn survival patterns
    - Heuristic evaluation based on resource levels and agent count
    """
    
    def __init__(self, use_rl: bool = False):
        """
        Initialize survival assessor.
        
        Args:
            use_rl: If True, use RL; if False, use heuristics
        """
        self.use_rl = use_rl
        if use_rl:
            self.q_table = {}  # Q-table for Q-Learning
            self.learning_rate = 0.1
            self.discount_factor = 0.9
        else:
            self.heuristic_weights = self._initialize_heuristic_weights()
    
    def _initialize_heuristic_weights(self) -> Dict[str, float]:
        """Initialize weights for heuristic evaluation."""
        return {
            "oxygen": 0.4,
            "calories": 0.3,
            "integrity": 0.2,
            "agent_count": 0.1
        }
    
    def assess_survival(self, colony_state: ColonyState) -> Dict[str, Any]:
        """
        Assess colony survival probability and risks.
        
        Main entry point for survival assessment.
        
        Args:
            colony_state: Current state to assess
            
        Returns:
            Assessment report with survival probability and risks
        """
        if self.use_rl:
            survival_prob = self._assess_with_rl(colony_state)
        else:
            survival_prob = self._assess_with_heuristics(colony_state)
        
        critical_threats = self._identify_critical_threats(colony_state)
        time_to_failure = self._estimate_time_to_failure(colony_state, survival_prob)
        
        return {
            "survival_probability": survival_prob,
            "critical_threats": critical_threats,
            "time_to_failure": time_to_failure,
            "assessment_method": "RL" if self.use_rl else "Heuristic"
        }
    
    def _assess_with_heuristics(self, colony_state: ColonyState) -> float:
        """
        Assess survival using heuristic evaluation.
        
        Simple weighted combination of resource levels and agent count.
        
        Args:
            colony_state: Current state
            
        Returns:
            Survival probability (0.0 to 1.0)
        """
        score = 0.0
        
        # Evaluate resource levels
        for resource, weight in self.heuristic_weights.items():
            if resource in colony_state.resources:
                level = colony_state.resources[resource]
                # Normalize to 0-1 (assuming max is 100)
                normalized = min(1.0, level / 100.0)
                score += weight * normalized
            elif resource == "agent_count":
                # Agent count contribution
                agent_count = len(colony_state.agents)
                # Assume 5 agents is "healthy"
                normalized = min(1.0, agent_count / 5.0)
                score += weight * normalized
        
        return max(0.0, min(1.0, score))
    
    def _assess_with_rl(self, colony_state: ColonyState) -> float:
        """
        Assess survival using Q-Learning.
        
        Uses learned Q-values to estimate survival probability.
        
        Args:
            colony_state: Current state
            
        Returns:
            Survival probability (0.0 to 1.0)
        """
        # TODO: Implement Q-Learning assessment
        # 1. Convert state to feature vector
        # 2. Look up or estimate Q-value for current state
        # 3. Convert Q-value to survival probability
        
        state_key = self._state_to_key(colony_state)
        
        if state_key in self.q_table:
            q_value = self.q_table[state_key]
            # Convert Q-value to probability (sigmoid or normalization)
            survival_prob = 1.0 / (1.0 + abs(q_value))
        else:
            # Unknown state, use heuristic as fallback
            survival_prob = self._assess_with_heuristics(colony_state)
        
        return survival_prob
    
    def _state_to_key(self, colony_state: ColonyState) -> str:
        """
        Convert colony state to a key for Q-table lookup.
        
        Args:
            colony_state: State to convert
            
        Returns:
            String key representing the state
        """
        # Create a simplified state representation
        resources = tuple(sorted(colony_state.resources.items()))
        agent_count = len(colony_state.agents)
        return f"{resources}_{agent_count}"
    
    def _identify_critical_threats(self, colony_state: ColonyState) -> List[str]:
        """
        Identify critical threats to colony survival.
        
        Args:
            colony_state: Current state
            
        Returns:
            List of threat descriptions
        """
        threats = []
        
        for resource, level in colony_state.resources.items():
            if level < 20.0:
                threats.append(f"{resource}_depletion")
            elif level < 50.0:
                threats.append(f"{resource}_low")
        
        if len(colony_state.agents) < 2:
            threats.append("insufficient_agents")
        
        if colony_state.resources.get("integrity", 100.0) < 30.0:
            threats.append("structural_failure_risk")
        
        return threats
    
    def _estimate_time_to_failure(self, colony_state: ColonyState, survival_prob: float) -> Optional[int]:
        """
        Estimate number of turns until colony failure.
        
        Args:
            colony_state: Current state
            survival_prob: Current survival probability
            
        Returns:
            Estimated turns until failure, or None if cannot estimate
        """
        if survival_prob > 0.8:
            return None  # Colony is healthy, no failure imminent
        
        # Simple linear projection based on resource depletion rates
        min_turns = float('inf')
        
        for resource, level in colony_state.resources.items():
            # Assume consumption rate of 5 per turn (adjust based on actual rates)
            consumption_rate = 5.0
            if consumption_rate > 0:
                turns_until_zero = level / consumption_rate
                min_turns = min(min_turns, turns_until_zero)
        
        return int(min_turns) if min_turns != float('inf') else None
    
    def update_rl(self, state: ColonyState, action: str, reward: float, next_state: ColonyState) -> None:
        """
        Update Q-table using Q-Learning update rule.
        
        Q(s,a) = Q(s,a) + α[r + γ*max(Q(s',a')) - Q(s,a)]
        
        Args:
            state: Previous state
            action: Action taken
            reward: Reward received
            next_state: Resulting state
        """
        if not self.use_rl:
            return
        
        state_key = self._state_to_key(state)
        next_state_key = self._state_to_key(next_state)
        
        # Initialize Q-values if needed
        if state_key not in self.q_table:
            self.q_table[state_key] = {}
        if next_state_key not in self.q_table:
            self.q_table[next_state_key] = {}
        
        # Get current Q-value
        current_q = self.q_table[state_key].get(action, 0.0)
        
        # Get max Q-value for next state
        max_next_q = max(self.q_table[next_state_key].values()) if self.q_table[next_state_key] else 0.0
        
        # Q-Learning update
        new_q = current_q + self.learning_rate * (reward + self.discount_factor * max_next_q - current_q)
        self.q_table[state_key][action] = new_q
