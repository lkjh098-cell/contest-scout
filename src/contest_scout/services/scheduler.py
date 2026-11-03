"""자동 Scout 스케줄러.

의존성을 늘리지 않으려고 cron/APScheduler 대신 스레드 하나로 처리한다. 30초마다
깨어나 "설정된 시각을 지났고 오늘 아직 안 돌았으면" 실행한다.

한계는 UI에도 그대로 적는다. **백엔드 프로세스가 떠 있는 동안에만** 동작한다.
맥을 껐다 켜면 다시 서버를 띄워야 한다.
"""

from __future__ import annotations

import logging
import threading
from datetime import date, datetime
from typing import Any

from contest_scout.services.scout import runner
from contest_scout.services.settings import load_settings

log = logging.getLogger(__name__)

TICK_SECONDS = 30


class Scheduler:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_run_date: date | None = None
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="scout-scheduler")
        self._thread.start()
        log.info("스케줄러 시작")

    def stop(self) -> None:
        self._stop.set()

    def status(self) -> dict[str, Any]:
        settings = load_settings()
        return {
            "thread_alive": self.running,
            "enabled": settings.schedule.enabled,
            "time": settings.schedule.time,
            "last_triggered": self._last_run_date.isoformat() if self._last_run_date else None,
            "next_run": self._next_run_label(settings.schedule.time, settings.schedule.enabled),
        }

    # ------------------------------------------------------------------ #
    def _next_run_label(self, hhmm: str, enabled: bool) -> str | None:
        if not enabled:
            return None
        target = _parse_time(hhmm)
        if target is None:
            return None
        now = datetime.now()
        today_target = now.replace(hour=target[0], minute=target[1], second=0, microsecond=0)
        if now < today_target and self._last_run_date != now.date():
            return today_target.isoformat(timespec="minutes")
        return today_target.replace(day=today_target.day).isoformat(timespec="minutes")

    def _loop(self) -> None:
        while not self._stop.wait(TICK_SECONDS):
            try:
                self._tick()
            except Exception:  # noqa: BLE001 - 스케줄러가 죽으면 안 된다
                log.exception("스케줄러 tick 실패")

    def _tick(self) -> None:
        settings = load_settings()
        if not settings.schedule.enabled:
            return
        target = _parse_time(settings.schedule.time)
        if target is None:
            return

        now = datetime.now()
        with self._lock:
            if self._last_run_date == now.date():
                return
            if (now.hour, now.minute) < target:
                return
            # 예약 시각을 놓친 채 서버가 켜진 경우에도 그날 안에 한 번은 돈다.
            self._last_run_date = now.date()

        if runner.is_running:
            log.info("이미 수집 중이라 예약 실행을 건너뜁니다")
            return
        log.info("예약 실행 시작 (%s)", settings.schedule.time)
        runner.start(trigger="schedule", settings=settings)


def _parse_time(raw: str) -> tuple[int, int] | None:
    try:
        hour, minute = raw.split(":")
        h, m = int(hour), int(minute)
    except (ValueError, AttributeError):
        return None
    if not (0 <= h < 24 and 0 <= m < 60):
        return None
    return h, m


scheduler = Scheduler()

__all__ = ["Scheduler", "scheduler"]
