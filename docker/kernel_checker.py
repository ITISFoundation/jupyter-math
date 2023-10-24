#!/home/jovyan/.venv/bin/python


import asyncio
import json
import requests
from datetime import datetime
import tornado
from contextlib import suppress
from typing import Final


KERNEL_BUSY_CHECK_INTERVAL_S: Final[float] = 5

class JupyterKernelChecker:
    BASE_URL = "http://localhost:8888"
    HEADERS = {"accept": "application/json"}

    def __init__(self) -> None:
        self.last_idle: datetime| None  = None
    
    def _get(self, path: str) -> dict:
        r = requests.get(f'{self.BASE_URL}{path}', headers=self.HEADERS)
        return r.json()

    def _are_kernels_busy(self)-> bool:
        json_response = self._get("/api/kernels")

        are_kernels_busy = False

        for kernel_data in json_response:
            kernel_id = kernel_data["id"]

            kernel_info = self._get(f"/api/kernels/{kernel_id}")
            if kernel_info["execution_state"] != "idle":
                are_kernels_busy = True

        return are_kernels_busy
    
    def check(self):
        are_kernels_busy = self._are_kernels_busy()
        
        if are_kernels_busy:
            self.last_idle = None

        if not are_kernels_busy and self.last_idle is None:
            self.last_idle = datetime.utcnow()

    
    def get_idle_seconds(self)-> float:
        if self.last_idle is None:
            return 0

        return (datetime.utcnow() - self.last_idle).total_seconds()
    
    async def run(self):
        while True:
            with suppress(Exception):
                self.check()
            await asyncio.sleep(KERNEL_BUSY_CHECK_INTERVAL_S)
        


kernel_checker = JupyterKernelChecker()


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        idle_seconds = kernel_checker.get_idle_seconds()
        response = (
            {"seconds_inactive" : idle_seconds if idle_seconds > 0 else None} 
        )
        self.write(json.dumps(response))


def make_app()-> tornado.web.Application:
    return tornado.web.Application([(r"/", MainHandler)])

async def main():
    app = make_app()
    app.listen(19597)
    asyncio.create_task(kernel_checker.run())
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
