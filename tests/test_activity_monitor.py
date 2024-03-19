import ctypes
import pytest
import socket
import threading
import psutil
import time

from concurrent.futures import ThreadPoolExecutor, wait
from multiprocessing import Array, Process
from tempfile import NamedTemporaryFile

from typing import Callable, Final, TYPE_CHECKING
from pytest_mock import MockFixture
from tenacity import AsyncRetrying
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed


if TYPE_CHECKING:
    from ..docker import activity_monitor
else:
    from _import_utils import allow_imports

    allow_imports()
    import activity_monitor


_LOCAL_LISTEN_PORT: Final[int] = 12345

pytestmark = pytest.mark.asyncio


class _ListenSocketServer:
    def __init__(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(("localhost", _LOCAL_LISTEN_PORT))
        self.server_socket.listen(100)  # max number of connections
        self.stop_event = threading.Event()

    def start(self):
        threading.Thread(target=self._accept_clients, daemon=True).start()

    def stop(self):
        self.stop_event.set()

    def _accept_clients(self):
        while not self.stop_event.is_set():
            client_socket, _ = self.server_socket.accept()
            threading.Thread(
                target=self._handle_client, daemon=True, args=(client_socket,)
            ).start()

    def _handle_client(self, client_socket):
        try:
            while not self.stop_event.is_set():
                data = client_socket.recv(1024)
                if not data:
                    break
        finally:
            client_socket.close()


class _ActivityGenerator:
    def __init__(self, *, network: bool, cpu: bool, disk: bool) -> None:
        self._process: Process | None = None

        _keep_running = True
        self.shared_array = Array(ctypes.c_bool, 4)
        self.shared_array[0] = network
        self.shared_array[1] = cpu
        self.shared_array[2] = disk
        self.shared_array[3] = _keep_running

    def __load_cpu(self) -> None:
        for _ in range(1000000):
            pass

    def __load_network(self) -> None:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(("localhost", _LOCAL_LISTEN_PORT))
        client_socket.sendall("mock_message_to_send".encode())
        client_socket.close()

    def __load_disk(self) -> None:
        with NamedTemporaryFile() as temp_file:
            temp_file.write(b"0" * 1024 * 1024)  # 1MB
            temp_file.read()

    def _run(self) -> None:
        with ThreadPoolExecutor(max_workers=3) as executor:
            while self.shared_array[3]:
                futures = []
                if self.shared_array[0]:
                    futures.append(executor.submit(self.__load_network))
                if self.shared_array[1]:
                    futures.append(executor.submit(self.__load_cpu))
                if self.shared_array[2]:
                    futures.append(executor.submit(self.__load_disk))

                wait(futures)
                time.sleep(0.01)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()

    def start(self) -> None:
        self._process = Process(target=self._run, daemon=True)
        self._process.start()

    def stop(self) -> None:
        self.shared_array[3] = False
        if self._process:
            self._process.join()

    def get_pid(self) -> int:
        assert self._process
        return self._process.pid


@pytest.fixture
def socket_server() -> None:
    socket_server = _ListenSocketServer()
    socket_server.start()
    yield None
    socket_server.stop()


@pytest.fixture
def mock__get_brother_processes(mocker: MockFixture) -> Callable:
    def _(pids: list[int]) -> None:
        mocker.patch(
            "activity_monitor._get_brother_processes",
            return_value=[psutil.Process(p) for p in pids],
        )

    return _


async def test_is_working(socket_server: None, mock__get_brother_processes: Callable):
    with _ActivityGenerator(network=False, cpu=False, disk=False) as activity_generator:
        mock__get_brother_processes([activity_generator.get_pid()])

        assert len(activity_monitor._get_brother_processes()) == 1

        # some tests
        with activity_monitor.CPUUsageMonitor(1, threshold=0) as cpu_usage_monitor:
            # poll for it to be idle since it takes some time
            async for attempt in AsyncRetrying(
                stop=stop_after_delay(3), wait=wait_fixed(0.1), reraise=True
            ):
                with attempt:
                    # TODO: figure out why test is wrong here
                    assert cpu_usage_monitor.is_busy is False

        # now we can test whatever here
