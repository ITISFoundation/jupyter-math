#!/home/jovyan/.venv/bin/python


import asyncio
import json
import psutil
import requests
import tornado
import time

from threading import Thread
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import suppress
from datetime import datetime
from typing import Final
from abc import abstractmethod


CHECK_INTERVAL_S: Final[float] = 5
CPU_USAGE_MONITORING_INTERVAL_S: Final[float] = 1
THRESHOLD_CPU_USAGE: Final[float] = 5  # percent in range [0, 100]


# Utilities
class AbstractIsBusyMonitor:
    def __init__(self, poll_interval: float) -> None:
        self._poll_interval: float = poll_interval
        self._keep_running: bool = True
        self._thread: Thread | None = None

        self.is_busy: bool = True

    @abstractmethod
    def _check_if_busy(self) -> bool:
        """Must be user defined and returns if current
        metric is to be considered busy

        Returns:
            bool: True if considered busy
        """

    def _worker(self) -> None:
        while self._keep_running:
            self.is_busy = self._check_if_busy()
            time.sleep(self._poll_interval)

    def start(self) -> None:
        self._thread = Thread(target=self._worker, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._keep_running = False
        if self._thread:
            self._thread.join()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()


def __get_children_processes(pid) -> list[psutil.Process]:
    try:
        return psutil.Process(pid).children(recursive=True)
    except psutil.NoSuchProcess:
        return []


def _get_brother_processes() -> list[psutil.Process]:
    # Returns the CPU usage of all processes except this one.
    # ASSUMPTIONS:
    # - `CURRENT_PROC` is a child of root process
    # - `CURRENT_PROC` does not create any child processes
    #
    # It looks for its brothers (and their children) p1 to pN in order
    # to compute real CPU usage.
    #   - CURRENT_PROC
    #   - p1
    #   ...
    #   - pN
    current_process = psutil.Process()
    parent_pid = current_process.ppid()
    children = __get_children_processes(parent_pid)
    return [c for c in children if c.pid != current_process.pid]


# Monitors


class JupyterKernelMonitor(AbstractIsBusyMonitor):
    BASE_URL = "http://localhost:8888"
    HEADERS = {"accept": "application/json"}

    def __init__(self, poll_interval: float) -> None:
        super().__init__(poll_interval=poll_interval)

    def _get(self, path: str) -> dict:
        r = requests.get(f"{self.BASE_URL}{path}", headers=self.HEADERS)
        return r.json()

    def _are_kernels_busy(self) -> bool:
        json_response = self._get("/api/kernels")

        are_kernels_busy = False

        for kernel_data in json_response:
            kernel_id = kernel_data["id"]

            kernel_info = self._get(f"/api/kernels/{kernel_id}")
            if kernel_info["execution_state"] != "idle":
                are_kernels_busy = True

        return are_kernels_busy

    def _check_if_busy(self) -> bool:
        return self._are_kernels_busy()


class CPUUsageMonitor(AbstractIsBusyMonitor):
    def __init__(self, poll_interval: float, *, threshold: float):
        super().__init__(poll_interval=poll_interval)
        self.threshold = threshold

    def _get_total_cpu_usage(self) -> float:
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(x.cpu_percent, CPU_USAGE_MONITORING_INTERVAL_S)
                for x in _get_brother_processes()
            ]
            return sum([future.result() for future in as_completed(futures)])

    def _check_if_busy(self) -> bool:
        return self._get_total_cpu_usage() >= self.threshold


class ActivityManager:
    def __init__(self, interval: float) -> None:
        self.interval = interval
        self.last_idle: datetime | None = None

        self.jupyter_kernel_monitor = JupyterKernelMonitor(CHECK_INTERVAL_S)
        self.cpu_usage_monitor = CPUUsageMonitor(
            CHECK_INTERVAL_S, threshold=THRESHOLD_CPU_USAGE
        )

    def check(self):
        is_busy = self.jupyter_kernel_monitor.is_busy or self.cpu_usage_monitor.is_busy

        if is_busy:
            self.last_idle = None

        if not is_busy and self.last_idle is None:
            self.last_idle = datetime.utcnow()

    def get_idle_seconds(self) -> float:
        if self.last_idle is None:
            return 0

        idle_seconds = (datetime.utcnow() - self.last_idle).total_seconds()
        return idle_seconds if idle_seconds > 0 else 0

    async def run(self):
        while True:
            with suppress(Exception):
                self.check()
            await asyncio.sleep(self.interval)


class DebugHandler(tornado.web.RequestHandler):
    def initialize(self, activity_manager: ActivityManager):
        self.activity_manager: ActivityManager = activity_manager

    async def get(self):
        assert self.activity_manager
        self.write(
            json.dumps(
                {
                    "seconds_inactive": self.activity_manager.get_idle_seconds(),
                    "cpu_usage": {
                        "is_busy": self.activity_manager.cpu_usage_monitor.is_busy,
                    },
                    "kernel_monitor": {
                        "is_busy": self.activity_manager.jupyter_kernel_monitor.is_busy
                    },
                }
            )
        )


class MainHandler(tornado.web.RequestHandler):
    def initialize(self, activity_manager: ActivityManager):
        self.activity_manager: ActivityManager = activity_manager

    async def get(self):
        assert self.activity_manager
        self.write(
            json.dumps({"seconds_inactive": self.activity_manager.get_idle_seconds()})
        )


def make_app(activity_manager) -> tornado.web.Application:
    return tornado.web.Application(
        [
            (r"/", MainHandler, dict(activity_manager=activity_manager)),
            (r"/debug", DebugHandler, dict(activity_manager=activity_manager)),
        ]
    )


async def main():
    activity_manager = ActivityManager(CHECK_INTERVAL_S)
    app = make_app(activity_manager)
    app.listen(19597)
    asyncio.create_task(activity_manager.run())
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
