import ctypes
import pytest
import socket
import threading
import psutil
import time

from concurrent.futures import ThreadPoolExecutor, wait
from multiprocessing import Array, Process
from tempfile import NamedTemporaryFile

from typing import Callable, Final, TYPE_CHECKING, Iterable
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
        self._process: Process | None = None

    def start(self):
        self._process = Process(target=self._accept_clients, daemon=True)
        self._process.start()

    def stop(self):
        if self._process:
            self._process.terminate()
            self._process.join()

    def _accept_clients(self):
        while True:
            client_socket, _ = self.server_socket.accept()
            threading.Thread(
                target=self._handle_client, daemon=True, args=(client_socket,)
            ).start()

    def _handle_client(self, client_socket):
        try:
            while True:
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
                time.sleep(0.1)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self) -> None:
        self._process = Process(target=self._run, daemon=True)
        self._process.start()

    def stop(self) -> None:
        _keep_running = False
        self.shared_array[3] = _keep_running
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
def mock__get_brother_processes(mocker: MockFixture) -> Callable[[list[int]], list[psutil.Process]]:
    def _get_processes(pids: list[int]) -> list[psutil.Process]:
        results = []
        for pid in pids:
            proc = psutil.Process(pid)
            assert proc.status()
            results.append(proc)
        return results

    def _(pids: list[int]) -> None:
        mocker.patch(
            "activity_monitor._get_brother_processes", return_value=_get_processes(pids)
        )

    return _


@pytest.fixture
def create_activity_generator() -> (
    Iterable[Callable[[bool, bool, bool], _ActivityGenerator]]
):
    created: list[_ActivityGenerator] = []

    def _(*, network: bool, cpu: bool, disk: bool) -> _ActivityGenerator:
        instance = _ActivityGenerator(network=network, cpu=cpu, disk=disk)
        instance.start()
        created.append(instance)
        return instance

    yield _

    for instance in created:
        instance.stop()


async def test_cpu_usage_monitor_not_busy(
    socket_server: None,
    mock__get_brother_processes: Callable[[list[int]], list[psutil.Process]],
    create_activity_generator: Callable[[bool, bool, bool], _ActivityGenerator],
):
    activity_generator = create_activity_generator(network=False, cpu=False, disk=False)
    mock__get_brother_processes([activity_generator.get_pid()])

    with activity_monitor.CPUUsageMonitor(1, threshold=5) as cpu_usage_monitor:
        async for attempt in AsyncRetrying(
            stop=stop_after_delay(5), wait=wait_fixed(0.1), reraise=True
        ):
            with attempt:
                assert cpu_usage_monitor.is_busy is False


async def test_cpu_usage_monitor_still_busy(
    socket_server: None,
    mock__get_brother_processes: Callable[[list[int]], list[psutil.Process]],
    create_activity_generator: Callable[[bool, bool, bool], _ActivityGenerator],
):
    activity_generator = create_activity_generator(network=False, cpu=True, disk=False)
    mock__get_brother_processes([activity_generator.get_pid()])

    with activity_monitor.CPUUsageMonitor(0.5, threshold=5) as cpu_usage_monitor:
        # wait for monitor to trigger
        time.sleep(1)

        # must still result busy
        assert cpu_usage_monitor.is_busy is True
