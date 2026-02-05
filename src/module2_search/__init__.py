"""
Module 2: Task Planning & Logistics Optimization

This module uses search algorithms to optimize task execution sequences.
It finds optimal paths and task assignments for agents.

Topics: Search (A*, IDA*, Beam Search)

Public API:
- ColonyGraph: Colony map for pathfinding
- PathResult: Result of pathfinding (path, cost, found)
- Task: Task to be assigned
- TaskAssignment: Task assigned to an agent (with path)
- TaskPlanner: Plans using A*, IDA*, Beam Search
"""

from src.module2_search.task_planner import (
    ColonyGraph,
    PathResult,
    Task,
    TaskAssignment,
    TaskPlanner,
)

__all__ = [
    "ColonyGraph",
    "PathResult",
    "Task",
    "TaskAssignment",
    "TaskPlanner",
]
