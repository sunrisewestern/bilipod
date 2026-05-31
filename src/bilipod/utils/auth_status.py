import threading
import time
from dataclasses import asdict, dataclass
from typing import Optional


@dataclass
class AuthStatusSnapshot:
    state: str = "idle"
    message: str = ""
    action_label: Optional[str] = None
    action_url: Optional[str] = None
    updated_at: float = 0.0


class AuthStatus:
    def __init__(self):
        self._lock = threading.Lock()
        self._snapshot = AuthStatusSnapshot()

    def set(
        self,
        state: str,
        message: str,
        action_label: Optional[str] = None,
        action_url: Optional[str] = None,
    ) -> None:
        with self._lock:
            self._snapshot = AuthStatusSnapshot(
                state=state,
                message=message,
                action_label=action_label,
                action_url=action_url,
                updated_at=time.time(),
            )

    def clear(self) -> None:
        with self._lock:
            self._snapshot = AuthStatusSnapshot(updated_at=time.time())

    def snapshot(self) -> dict:
        with self._lock:
            return asdict(self._snapshot)


AUTH_STATUS = AuthStatus()


def set_auth_status(
    state: str,
    message: str,
    action_label: Optional[str] = None,
    action_url: Optional[str] = None,
) -> None:
    AUTH_STATUS.set(state, message, action_label, action_url)


def clear_auth_status() -> None:
    AUTH_STATUS.clear()


def get_auth_status() -> dict:
    return AUTH_STATUS.snapshot()
