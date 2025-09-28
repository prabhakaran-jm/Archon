"""
Circuit Breaker Pattern Implementation for Archon
Provides resilience for external API calls with automatic failure detection and recovery
"""

import time
import logging
from enum import Enum
from typing import Callable, Any, Optional
from dataclasses import dataclass
from functools import wraps

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing fast
    HALF_OPEN = "half_open"  # Testing if service recovered

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5          # Failures before opening circuit
    recovery_timeout: int = 60          # Seconds before trying half-open
    success_threshold: int = 3          # Successes needed to close circuit
    timeout: int = 30                   # Request timeout in seconds
    expected_exception: type = Exception # Exception type to count as failures

class CircuitBreaker:
    """Circuit breaker implementation"""
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_success_time = None
        
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker {self.name} transitioning to HALF_OPEN")
            else:
                raise CircuitBreakerOpenException(f"Circuit breaker {self.name} is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.config.expected_exception as e:
            self._on_failure()
            raise e
        except Exception as e:
            # Unexpected exceptions don't count as failures
            logger.warning(f"Unexpected exception in circuit breaker {self.name}: {e}")
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.config.recovery_timeout
    
    def _on_success(self):
        """Handle successful call"""
        self.last_success_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                logger.info(f"Circuit breaker {self.name} closed after successful calls")
        else:
            # Reset failure count on success
            self.failure_count = 0
    
    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker {self.name} opened after {self.failure_count} failures")
    
    def get_state(self) -> dict:
        """Get current circuit breaker state"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time
        }

class CircuitBreakerOpenException(Exception):
    """Exception raised when circuit breaker is open"""
    pass

# Global circuit breaker instances
_circuit_breakers = {}

def get_circuit_breaker(name: str, config: CircuitBreakerConfig = None) -> CircuitBreaker:
    """Get or create circuit breaker instance"""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name, config)
    return _circuit_breakers[name]

def circuit_breaker(name: str, config: CircuitBreakerConfig = None):
    """Decorator for circuit breaker pattern"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cb = get_circuit_breaker(name, config)
            return cb.call(func, *args, **kwargs)
        return wrapper
    return decorator

# Pre-configured circuit breakers for common services
def get_github_circuit_breaker() -> CircuitBreaker:
    """Get circuit breaker for GitHub API calls"""
    config = CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=30,
        success_threshold=2,
        timeout=15,
        expected_exception=Exception
    )
    return get_circuit_breaker("github_api", config)

def get_aws_circuit_breaker() -> CircuitBreaker:
    """Get circuit breaker for AWS API calls"""
    config = CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=60,
        success_threshold=3,
        timeout=30,
        expected_exception=Exception
    )
    return get_circuit_breaker("aws_api", config)

def get_bedrock_circuit_breaker() -> CircuitBreaker:
    """Get circuit breaker for Bedrock API calls"""
    config = CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=45,
        success_threshold=2,
        timeout=60,
        expected_exception=Exception
    )
    return get_circuit_breaker("bedrock_api", config)

def get_all_circuit_breaker_states() -> dict:
    """Get states of all circuit breakers"""
    return {name: cb.get_state() for name, cb in _circuit_breakers.items()}
