"""
Rate limiting simples em memória para tentativas de login.

Adequado para uma única instância do backend. Se o sistema crescer para
múltiplas réplicas atrás de um load balancer, substitua por um contador
compartilhado (ex: Redis) para que o limite seja respeitado globalmente.
"""

import threading
import time

_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 15 * 60

_lock = threading.Lock()
_attempts: dict[str, list[float]] = {}


def _key(email: str, ip: str | None) -> str:
    return f"{email.lower()}|{ip or 'unknown'}"


def too_many_failed_attempts(email: str, ip: str | None) -> bool:
    with _lock:
        now = time.time()
        history = _attempts.get(_key(email, ip), [])
        history = [t for t in history if now - t < _WINDOW_SECONDS]
        return len(history) >= _MAX_ATTEMPTS


def register_failed_attempt(email: str, ip: str | None) -> None:
    with _lock:
        k = _key(email, ip)
        now = time.time()
        history = [t for t in _attempts.get(k, []) if now - t < _WINDOW_SECONDS]
        history.append(now)
        _attempts[k] = history


def reset_attempts(email: str, ip: str | None) -> None:
    with _lock:
        _attempts.pop(_key(email, ip), None)
