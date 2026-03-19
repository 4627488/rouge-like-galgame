"""Async generation pipeline — prefetch next segment in a background thread."""

from __future__ import annotations

import logging
import sys
import threading
import time
from typing import TYPE_CHECKING

from phantom_seed.ai.protocol import SceneData

if TYPE_CHECKING:
    from phantom_seed.core.coordinator import GameCoordinator

log = logging.getLogger(__name__)


class _TerminalProgressBar:
    """Single-line terminal progress bar, inspired by pip style output."""

    def __init__(self, title: str, total: int) -> None:
        self.title = title
        self.total = max(1, total)
        self.width = 28
        self._lock = threading.Lock()
        self._started_at = time.time()

    def update(self, step: int, message: str = "") -> None:
        with self._lock:
            step = min(max(step, 0), self.total)
            ratio = step / self.total
            percent = int(ratio * 100)
            filled = int(self.width * ratio)
            bar = "#" * filled + "-" * (self.width - filled)
            elapsed = time.time() - self._started_at
            line = (
                f"\r{self.title:<8} |{bar}| {percent:>3d}% "
                f"{elapsed:>5.1f}s {message:<20}"
            )
            print(line, end="", file=sys.stdout, flush=True)

    def close(self, ok: bool, message: str) -> None:
        with self._lock:
            final = self.total if ok else max(0, self.total - 1)
            ratio = final / self.total
            percent = int(ratio * 100)
            filled = int(self.width * ratio)
            bar = "#" * filled + "-" * (self.width - filled)
            elapsed = time.time() - self._started_at
            line = (
                f"\r{self.title:<8} |{bar}| {percent:>3d}% "
                f"{elapsed:>5.1f}s {message:<20}"
            )
            print(line, end="", file=sys.stdout, flush=True)
            print(file=sys.stdout, flush=True)


class AsyncPipeline:
    """Manages background prefetching of AI-generated content.

    Uses a single worker thread to generate the next scene while
    the player reads the current one. Pygame can't use asyncio
    easily, so we use threading instead.
    """

    def __init__(self, coordinator: GameCoordinator) -> None:
        self.coordinator = coordinator
        self._prefetched: SceneData | None = None
        self._error: Exception | None = None
        self._lock = threading.Lock()
        self._worker: threading.Thread | None = None
        self._generating = False
        self._progress_bar: _TerminalProgressBar | None = None
        self._progress_total = 0

    @property
    def is_generating(self) -> bool:
        return self._generating

    @property
    def has_result(self) -> bool:
        with self._lock:
            return self._prefetched is not None or self._error is not None

    def _start_progress(self, title: str, total: int) -> None:
        self._progress_total = max(1, total)
        self._progress_bar = _TerminalProgressBar(title, self._progress_total)
        self._progress_bar.update(0, "开始")

    def _on_progress(self, step: int, total: int, message: str) -> None:
        if total != self._progress_total or self._progress_bar is None:
            self._start_progress("生成中", total)
        assert self._progress_bar is not None
        self._progress_bar.update(step, message)

    def _finish_progress(self, ok: bool, message: str) -> None:
        if self._progress_bar is not None:
            self._progress_bar.close(ok=ok, message=message)
        self._progress_bar = None
        self._progress_total = 0

    def request_init(self, seed: str) -> None:
        """Start game initialization in the background with terminal progress."""
        if self._generating:
            log.warning("Generation already in progress, ignoring init request")
            return

        self._prefetched = None
        self._error = None
        self._generating = True
        self._start_progress("初始化", 5)

        self._worker = threading.Thread(
            target=self._init_worker,
            args=(seed,),
            daemon=True,
        )
        self._worker.start()

    def request_next(
        self, player_choice: str = "", choice_delta: dict[str, int] | None = None
    ) -> None:
        """Start generating the next scene in the background."""
        if self._generating:
            log.warning("Generation already in progress, ignoring request")
            return

        self._prefetched = None
        self._error = None
        self._generating = True
        self._start_progress("生成中", 6)

        self._worker = threading.Thread(
            target=self._generate_worker,
            args=(player_choice, choice_delta),
            daemon=True,
        )
        self._worker.start()

    def _init_worker(self, seed: str) -> None:
        ok = False
        try:
            scene = self.coordinator.init_game(seed, progress_cb=self._on_progress)
            with self._lock:
                self._prefetched = scene
            ok = True
        except Exception as e:
            log.exception("Background init failed")
            with self._lock:
                self._error = e
        finally:
            self._generating = False
            self._finish_progress(ok, "完成" if ok else "失败")

    def _generate_worker(
        self, player_choice: str, choice_delta: dict[str, int] | None
    ) -> None:
        ok = False
        try:
            scene = self.coordinator.get_next_scene(
                player_choice,
                choice_delta,
                progress_cb=self._on_progress,
            )
            with self._lock:
                self._prefetched = scene
            ok = True
        except Exception as e:
            log.exception("Background generation failed")
            with self._lock:
                self._error = e
        finally:
            self._generating = False
            self._finish_progress(ok, "完成" if ok else "失败")

    def collect(self) -> SceneData | None:
        """Collect the prefetched result. Returns None if not ready or failed."""
        with self._lock:
            if self._error:
                log.error("Prefetch had error: %s", self._error)
                self._error = None
                return None
            result = self._prefetched
            self._prefetched = None
            return result

    def wait(self, timeout: float = 30.0) -> SceneData | None:
        """Block until the prefetched result is ready."""
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=timeout)
        return self.collect()
