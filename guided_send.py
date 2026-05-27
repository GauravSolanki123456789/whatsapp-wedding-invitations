"""Guided Send — one guest at a time with anti-spam delays (phone & hosted app)."""

from __future__ import annotations

import random
import time

from constants import SESSION_GUIDED_COOLDOWN_UNTIL


def cooldown_seconds(delay_min: int, delay_max: int) -> float:
    if delay_max <= 0:
        return 0.0
    if delay_min <= 0:
        return random.uniform(0, delay_max)
    return random.uniform(delay_min, delay_max)


def cooldown_remaining(session_state: dict) -> int:
    until = float(session_state.get(SESSION_GUIDED_COOLDOWN_UNTIL, 0))
    return max(0, int(until - time.time()))


def start_cooldown(session_state: dict, delay_min: int, delay_max: int) -> float:
    pause = cooldown_seconds(delay_min, delay_max)
    session_state[SESSION_GUIDED_COOLDOWN_UNTIL] = time.time() + pause
    return pause


def next_pending_guest(
    mobile_numbers: list[str],
    sent_numbers: set[str],
) -> tuple[str | None, int, int, int]:
    """
    Return (next_number, guest_position_1based, pending_count, total_count).
    guest_position is the position in the full list (for display).
    """
    total = len(mobile_numbers)
    pending = [number for number in mobile_numbers if number not in sent_numbers]
    if not pending:
        return None, 0, 0, total
    number = pending[0]
    position = mobile_numbers.index(number) + 1
    return number, position, len(pending), total
