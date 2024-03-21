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
THREAD_EXECUTOR_WORKERS: Final[int] = 10

BUSY_USAGE_THRESHOLD_CPU: Final[float] = 5  # percent in range [0, 100]
BUSY_USAGE_THRESHOLD_DISK_READ: Final[int] = 0  # in bytes
BUSY_USAGE_THRESHOLD_DISK_WRITE: Final[int] = 0  # in bytes


# Utilities
class AbstractIsBusyMonitor:
    def __init__(self, poll_interval: float) -> None:
        self._poll_interval: float = poll_interval
        self._keep_running: bool = True
        self._thread: Thread | None = None

        self.is_busy: bool = True
        self.thread_executor = ThreadPoolExecutor(max_workers=THREAD_EXECUTOR_WORKERS)

    @abstractmethod
    def _check_if_busy(self) -> bool:
        """Must be user defined and returns if current
        metric is to be considered busy

        Returns:
            bool: True if considered busy
        """

    def _worker(self) -> None:
        while self._keep_running:
            with suppress(Exception):
                self.is_busy = self._check_if_busy()
            time.sleep(self._poll_interval)

    def start(self) -> None:
        self._thread = Thread(target=self._worker, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._keep_running = False
        if self._thread:
            self._thread.join()
        self.thread_executor.shutdown(wait=True)

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
    CPU_USAGE_MONITORING_INTERVAL_S: Final[float] = 1

    def __init__(self, poll_interval: float, *, busy_threshold: float):
        super().__init__(poll_interval=poll_interval)
        self.busy_threshold = busy_threshold

    def get_total_cpu_usage(self) -> float:
        futures = [
            self.thread_executor.submit(
                x.cpu_percent, self.CPU_USAGE_MONITORING_INTERVAL_S
            )
            for x in _get_brother_processes()
        ]
        return sum([future.result() for future in as_completed(futures)])

    def _check_if_busy(self) -> bool:
        return self.get_total_cpu_usage() > self.busy_threshold


class DiskUsageMonitor(AbstractIsBusyMonitor):
    DISK_USAGE_MONITORING_INTERVAL_S: Final[float] = 1

    def __init__(
        self,
        poll_interval: float,
        *,
        read_usage_threshold: float,
        write_usage_threshold: float,
    ):
        super().__init__(poll_interval=poll_interval)
        self.read_usage_threshold = read_usage_threshold
        self.write_usage_threshold = write_usage_threshold
        self.executor = ThreadPoolExecutor(max_workers=THREAD_EXECUTOR_WORKERS)

    def _get_process_disk_usage(self, proc: psutil.Process) -> tuple[int, int]:
        io_start = proc.io_counters()
        time.sleep(self.DISK_USAGE_MONITORING_INTERVAL_S)
        io_end = proc.io_counters()

        # Calculate the differences
        read_bytes = io_end.read_bytes - io_start.read_bytes
        write_bytes = io_end.write_bytes - io_start.write_bytes
        return read_bytes, write_bytes

    def get_total_disk_usage(self) -> tuple[int, int]:
        futures = [
            self.thread_executor.submit(self._get_process_disk_usage, x)
            for x in _get_brother_processes()
        ]

        disk_usage: list[tuple[int, int]] = [
            future.result() for future in as_completed(futures)
        ]
        read_bytes: int = 0
        write_bytes: int = 0
        for read, write in disk_usage:
            read_bytes += read
            write_bytes += write

        return read_bytes, write_bytes

    def _check_if_busy(self) -> bool:
        read_bytes, write_bytes = self.get_total_disk_usage()
        return (
            read_bytes > self.read_usage_threshold
            or write_bytes > self.write_usage_threshold
        )


class ActivityManager:
    def __init__(self, interval: float) -> None:
        self.interval = interval
        self.last_idle: datetime | None = None

        self.jupyter_kernel_monitor = JupyterKernelMonitor(CHECK_INTERVAL_S)
        self.cpu_usage_monitor = CPUUsageMonitor(
            CHECK_INTERVAL_S, busy_threshold=BUSY_USAGE_THRESHOLD_CPU
        )
        self.disk_usage_monitor = DiskUsageMonitor(
            CHECK_INTERVAL_S,
            read_usage_threshold=BUSY_USAGE_THRESHOLD_DISK_READ,
            write_usage_threshold=BUSY_USAGE_THRESHOLD_DISK_WRITE,
        )

    def check(self):
        is_busy = (
            self.jupyter_kernel_monitor.is_busy
            or self.cpu_usage_monitor.is_busy
            or self.disk_usage_monitor.is_busy
        )

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
        self.jupyter_kernel_monitor.start()
        self.cpu_usage_monitor.start()
        self.disk_usage_monitor.start()
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
                        "total": self.activity_manager.cpu_usage_monitor.get_total_cpu_usage(),
                    },
                    "disk_usage": {
                        "is_busy": self.activity_manager.disk_usage_monitor.is_busy,
                        "total": self.activity_manager.disk_usage_monitor.get_total_disk_usage(),
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


async def make_app() -> tornado.web.Application:
    activity_manager = ActivityManager(CHECK_INTERVAL_S)
    app = tornado.web.Application(
        [
            (r"/", MainHandler, {"activity_manager": activity_manager}),
            (r"/debug", DebugHandler, {"activity_manager": activity_manager}),
        ]
    )
    asyncio.create_task(activity_manager.run())
    return app


async def main():
    app = await make_app()
    app.listen(19597)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
