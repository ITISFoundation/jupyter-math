import asyncio
import pytest
import psutil
import requests
import tornado.web
import tornado.httpserver
import tornado.ioloop
import threading
import pytest_asyncio

from queue import Queue
from typing import Callable, TYPE_CHECKING
from pytest_mock import MockFixture
from tenacity import AsyncRetrying
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from conftest import _ActivityGenerator

if TYPE_CHECKING:
    from ..docker import activity_monitor
else:
    from _import_utils import allow_imports

    allow_imports()
    import activity_monitor

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock__get_brother_processes(
    mocker: MockFixture,
) -> Callable[[list[int]], list[psutil.Process]]:
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


async def test_cpu_usage_monitor_not_busy(
    socket_server: None,
    mock__get_brother_processes: Callable[[list[int]], list[psutil.Process]],
    create_activity_generator: Callable[[bool, bool, bool], _ActivityGenerator],
):
    activity_generator = create_activity_generator(network=False, cpu=False, disk=False)
    mock__get_brother_processes([activity_generator.get_pid()])

    with activity_monitor.CPUUsageMonitor(1, busy_threshold=5) as cpu_usage_monitor:
        async for attempt in AsyncRetrying(
            stop=stop_after_delay(5), wait=wait_fixed(0.1), reraise=True
        ):
            with attempt:
                assert cpu_usage_monitor.get_total_cpu_usage() == 0
                assert cpu_usage_monitor.is_busy is False


async def test_cpu_usage_monitor_still_busy(
    socket_server: None,
    mock__get_brother_processes: Callable[[list[int]], list[psutil.Process]],
    create_activity_generator: Callable[[bool, bool, bool], _ActivityGenerator],
):
    activity_generator = create_activity_generator(network=False, cpu=True, disk=False)
    mock__get_brother_processes([activity_generator.get_pid()])

    with activity_monitor.CPUUsageMonitor(0.5, busy_threshold=5) as cpu_usage_monitor:
        # wait for monitor to trigger
        await asyncio.sleep(1)

        # must still result busy
        assert cpu_usage_monitor.get_total_cpu_usage() > 0
        assert cpu_usage_monitor.is_busy is True


async def test_disk_usage_monitor_not_busy(
    socket_server: None,
    mock__get_brother_processes: Callable[[list[int]], list[psutil.Process]],
    create_activity_generator: Callable[[bool, bool, bool], _ActivityGenerator],
):
    activity_generator = create_activity_generator(network=False, cpu=False, disk=False)
    mock__get_brother_processes([activity_generator.get_pid()])

    with activity_monitor.DiskUsageMonitor(
        0.5, read_usage_threshold=0, write_usage_threshold=0
    ) as disk_usage_monitor:
        async for attempt in AsyncRetrying(
            stop=stop_after_delay(5), wait=wait_fixed(0.1), reraise=True
        ):
            with attempt:
                read_bytes, write_bytes = disk_usage_monitor.get_total_disk_usage()
                assert read_bytes == 0
                assert write_bytes == 0
                assert disk_usage_monitor.is_busy is False


async def test_disk_usage_monitor_still_busy(
    socket_server: None,
    mock__get_brother_processes: Callable[[list[int]], list[psutil.Process]],
    create_activity_generator: Callable[[bool, bool, bool], _ActivityGenerator],
):
    activity_generator = create_activity_generator(network=False, cpu=False, disk=True)
    mock__get_brother_processes([activity_generator.get_pid()])

    with activity_monitor.DiskUsageMonitor(
        0.5, read_usage_threshold=0, write_usage_threshold=0
    ) as disk_usage_monitor:
        # wait for monitor to trigger
        await asyncio.sleep(1)
        _, write_bytes = disk_usage_monitor.get_total_disk_usage()
        # NOTE: due to os disk cache reading is not reliable not testing it
        assert write_bytes > 0

        # must still result busy
        assert disk_usage_monitor.is_busy is True


@pytest_asyncio.fixture
async def server_url() -> str:
    return "http://localhost:8899"


@pytest.fixture
def mock_jupyter_kernel_monitor(mocker: MockFixture) -> None:
    activity_monitor.JupyterKernelMonitor._are_kernels_busy = lambda _: False


@pytest_asyncio.fixture
async def tornado_server(mock_jupyter_kernel_monitor: None, server_url: str) -> None:
    app = await activity_monitor.make_app()

    stop_queue = Queue()

    def _run_server_worker():
        http_server = tornado.httpserver.HTTPServer(app)
        http_server.listen(8899)
        current_io_loop = tornado.ioloop.IOLoop.current()

        def _queue_stopper() -> None:
            stop_queue.get()
            current_io_loop.stop()

        stopping_thread = threading.Thread(target=_queue_stopper, daemon=True)
        stopping_thread.start()

        current_io_loop.start()
        stopping_thread.join()

    thread = threading.Thread(target=_run_server_worker, daemon=True)
    thread.start()

    # ensure server is running
    async for attempt in AsyncRetrying(
        stop=stop_after_delay(3), wait=wait_fixed(0.1), reraise=True
    ):
        with attempt:
            result = requests.get(f"{server_url}/", timeout=1)
            assert result.status_code == 200, result.text

    yield None

    stop_queue.put(None)
    thread.join(timeout=1)

    with pytest.raises(requests.exceptions.ReadTimeout):
        requests.get(f"{server_url}/", timeout=1)


@pytest.fixture
def mock_check_interval(mocker: MockFixture) -> None:
    mocker.patch("activity_monitor.CHECK_INTERVAL_S", new=1)
    assert activity_monitor.CHECK_INTERVAL_S == 1


@pytest.mark.asyncio
async def test_tornado_server_ok(
    mock_check_interval: None, tornado_server: None, server_url: str
):
    result = requests.get(f"{server_url}/", timeout=5)
    assert result.status_code == 200


async def test_activity_monitor_becomes_not_busy(
    mock_check_interval: None,
    socket_server: None,
    mock__get_brother_processes: Callable[[list[int]], list[psutil.Process]],
    create_activity_generator: Callable[[bool, bool, bool], _ActivityGenerator],
    tornado_server: None,
    server_url: str,
):
    activity_generator = create_activity_generator(network=False, cpu=False, disk=False)
    mock__get_brother_processes([activity_generator.get_pid()])

    async for attempt in AsyncRetrying(
        stop=stop_after_delay(10), wait=wait_fixed(0.1), reraise=True
    ):
        with attempt:
            # check that all become not busy
            result = requests.get(f"{server_url}/debug", timeout=5)
            assert result.status_code == 200
            debug_response = result.json()
            assert debug_response["cpu_usage"]["is_busy"] is False
            assert debug_response["disk_usage"]["is_busy"] is False
            assert debug_response["kernel_monitor"]["is_busy"] is False

            result = requests.get(f"{server_url}/", timeout=2)
            assert result.status_code == 200
            response = result.json()
            assert response["seconds_inactive"] > 0
