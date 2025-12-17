from enum import Enum
from typing import Dict, Set, Optional
import logging

logger = logging.getLogger(__name__)


class ProcessingRunState(str, Enum):
    """
    State machine for ProcessingRun lifecycle.
    
    Authoritative definition from data-model.md.
    Constitution II: State Machine-Driven Processing
    
    Valid transitions:
    - pending → running, failed
    - running → completed, failed
    - completed → (terminal state, no transitions)
    - failed → (terminal state, no transitions)
    
    Invariant: Transitions are append-only. No state may be skipped.
    """
    PENDING = "pending"      # Created, awaiting execution
    RUNNING = "running"      # At least one StepRun active
    COMPLETED = "completed"  # All StepRuns succeeded
    FAILED = "failed"        # At least one StepRun failed (terminal)
    
    @classmethod
    def valid_transitions(cls) -> Dict[str, Set[str]]:
        """Return mapping of state → set of valid next states"""
        return {
            cls.PENDING: {cls.RUNNING, cls.FAILED},
            cls.RUNNING: {cls.COMPLETED, cls.FAILED},
            cls.COMPLETED: set(),  # Terminal state
            cls.FAILED: set(),     # Terminal state
        }
    
    @classmethod
    def is_terminal(cls, state: 'ProcessingRunState') -> bool:
        """Check if state is terminal (no further transitions allowed)"""
        return state in {cls.COMPLETED, cls.FAILED}


class StepRunState(str, Enum):
    """
    State machine for StepRun lifecycle with retry support.
    
    Authoritative definition from data-model.md.
    Constitution II: State Machine-Driven Processing
    
    Valid transitions:
    - pending → running, failed_terminal
    - running → completed, failed_retryable, failed_terminal
    - completed → (terminal state)
    - failed_retryable → running (retry allowed)
    - failed_terminal → (terminal state)
    
    Invariant: Same StepRun ID can transition failed_retryable → running → completed
    on retry. Idempotency key ensures logical idempotence even across physical retries.
    """
    PENDING = "pending"                          # Created, awaiting execution
    RUNNING = "running"                          # Currently executing
    COMPLETED = "completed"                      # Succeeded
    FAILED_RETRYABLE = "failed_retryable"        # Failed but can retry
    FAILED_TERMINAL = "failed_terminal"          # Failed permanently
    
    @classmethod
    def valid_transitions(cls) -> Dict[str, Set[str]]:
        """Return mapping of state → set of valid next states"""
        return {
            cls.PENDING: {cls.RUNNING, cls.FAILED_TERMINAL},
            cls.RUNNING: {cls.COMPLETED, cls.FAILED_RETRYABLE, cls.FAILED_TERMINAL},
            cls.COMPLETED: set(),  # Terminal state
            cls.FAILED_RETRYABLE: {cls.RUNNING},  # Retry allowed
            cls.FAILED_TERMINAL: set(),  # Terminal state
        }
    
    @classmethod
    def is_terminal(cls, state: 'StepRunState') -> bool:
        """Check if state is terminal (no further transitions allowed except retry)"""
        return state in {cls.COMPLETED, cls.FAILED_TERMINAL}
    
    @classmethod
    def is_retryable(cls, state: 'StepRunState') -> bool:
        """Check if state allows retry"""
        return state == cls.FAILED_RETRYABLE


class InvalidStateTransitionError(Exception):
    """Raised when attempting an invalid state transition"""
    pass


def validate_processing_run_transition(
    current_state: ProcessingRunState,
    new_state: ProcessingRunState
) -> None:
    """
    Validate ProcessingRun state transition.
    
    Args:
        current_state: Current state
        new_state: Desired new state
        
    Raises:
        InvalidStateTransitionError: If transition is not allowed
    """
    valid_next_states = ProcessingRunState.valid_transitions()[current_state]
    
    if new_state not in valid_next_states:
        error_msg = (
            f"Invalid ProcessingRun state transition: "
            f"{current_state} → {new_state}. "
            f"Valid transitions from {current_state}: {valid_next_states}"
        )
        logger.error(error_msg)
        raise InvalidStateTransitionError(error_msg)
    
    logger.info(f"Valid ProcessingRun state transition: {current_state} → {new_state}")


def validate_step_run_transition(
    current_state: StepRunState,
    new_state: StepRunState
) -> None:
    """
    Validate StepRun state transition.
    
    Args:
        current_state: Current state
        new_state: Desired new state
        
    Raises:
        InvalidStateTransitionError: If transition is not allowed
    """
    valid_next_states = StepRunState.valid_transitions()[current_state]
    
    if new_state not in valid_next_states:
        error_msg = (
            f"Invalid StepRun state transition: "
            f"{current_state} → {new_state}. "
            f"Valid transitions from {current_state}: {valid_next_states}"
        )
        logger.error(error_msg)
        raise InvalidStateTransitionError(error_msg)
    
    logger.info(f"Valid StepRun state transition: {current_state} → {new_state}")


def log_state_transition(
    entity_type: str,
    entity_id: str,
    from_state: str,
    to_state: str,
    reason: Optional[str] = None
) -> None:
    """
    Log state transition for audit trail.
    
    Args:
        entity_type: "ProcessingRun" or "StepRun"
        entity_id: ID of the entity
        from_state: Previous state
        to_state: New state
        reason: Optional reason for transition
    """
    log_msg = f"{entity_type} {entity_id}: {from_state} → {to_state}"
    if reason:
        log_msg += f" (reason: {reason})"
    
    logger.info(log_msg)
