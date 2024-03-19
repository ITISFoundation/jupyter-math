#!/home/jovyan/.venv/bin/python


# How does this work?
# 1. controls that the service is not busy at regular intervals
# 2a. cheks if kernels are busy
# 2b. checks total CPU usage of all children processes is >= THRESHOLD_CPU_USAGE
# 3. if either of the above checks if True the service will result as busy


import asyncio
import json
import psutil
import requests
import tornado
import subprocess

from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import suppress
from datetime import datetime
from typing import Final


CHECK_INTERVAL_S: Final[float] = 5
CPU_USAGE_MONITORING_INTERVAL_S: Final[float] = 1
THRESHOLD_CPU_USAGE: Final[float] = 5  # percent in range [0, 100]


class JupyterKernelMonitor:
    BASE_URL = "http://localhost:8888"
    HEADERS = {"accept": "application/json"}

    def _get(self, path: str) -> dict:
        r = requests.get(f"{self.BASE_URL}{path}", headers=self.HEADERS)
        return r.json()

    def are_kernels_busy(self) -> bool:
        json_response = self._get("/api/kernels")

        are_kernels_busy = False

        for kernel_data in json_response:
            kernel_id = kernel_data["id"]

            kernel_info = self._get(f"/api/kernels/{kernel_id}")
            if kernel_info["execution_state"] != "idle":
                are_kernels_busy = True

        return are_kernels_busy


class CPUUsageMonitor:
    def __init__(self, threshold: float):
        self.threshold = threshold

    def _get_children_processes(self, pid) -> list[psutil.Process]:
        try:
            return psutil.Process(pid).children(recursive=True)
        except psutil.NoSuchProcess:
            return []

    def _get_brother_processes(self) -> list[psutil.Process]:
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
        children = self._get_children_processes(parent_pid)
        return [c for c in children if c.pid != current_process.pid]

    def _get_cpu_usage(self, pid: int) -> float:
        cmd = f"ps -p {pid} -o %cpu --no-headers"
        output = subprocess.check_output(cmd, shell=True, universal_newlines=True)
        try:
            return float(output)
        except ValueError:
            print(f"Could not parse {pid} cpu usage: {output}")
            return float(0)

    def _get_total_cpu_usage(self) -> float:
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(x.cpu_percent, CPU_USAGE_MONITORING_INTERVAL_S)
                for x in self._get_brother_processes()
            ]
            return sum([future.result() for future in as_completed(futures)])

    def are_children_busy(self) -> bool:
        return self._get_total_cpu_usage() >= self.threshold


class ActivityManager:
    def __init__(self, interval: float) -> None:
        self.interval = interval
        self.last_idle: datetime | None = None

        self.jupyter_kernel_monitor = JupyterKernelMonitor()
        self.cpu_usage_monitor = CPUUsageMonitor(THRESHOLD_CPU_USAGE)

    def check(self):
        is_busy = (
            self.jupyter_kernel_monitor.are_kernels_busy()
            or self.cpu_usage_monitor.are_children_busy()
        )

        if is_busy:
            self.last_idle = None

        if not is_busy and self.last_idle is None:
            self.last_idle = datetime.utcnow()

    def get_idle_seconds(self) -> float:
        if self.last_idle is None:
            return 0

        return (datetime.utcnow() - self.last_idle).total_seconds()

    async def run(self):
        while True:
            with suppress(Exception):
                self.check()
            await asyncio.sleep(self.interval)


activity_manager = ActivityManager(CHECK_INTERVAL_S)


class DebugHandler(tornado.web.RequestHandler):
    def get(self):
        self.write(
            json.dumps(
                {
                    "cpu_usage": {
                        "current": activity_manager.cpu_usage_monitor._get_total_cpu_usage(),
                        "busy": activity_manager.cpu_usage_monitor.are_children_busy(),
                    },
                    "kernal_monitor": {
                        "busy": activity_manager.jupyter_kernel_monitor.are_kernels_busy()
                    },
                }
            )
        )


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        idle_seconds = activity_manager.get_idle_seconds()
        seconds_inactive = idle_seconds if idle_seconds > 0 else 0

        self.write(json.dumps({"seconds_inactive": seconds_inactive}))


def make_app() -> tornado.web.Application:
    return tornado.web.Application(
        [
            (r"/", MainHandler),
            (r"/debug", DebugHandler),
        ]
    )


async def main():
    app = make_app()
    app.listen(19597)
    asyncio.create_task(activity_manager.run())
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
