import pytest
import psutil
import time


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
                assert cpu_usage_monitor._get_total_cpu_usage() == 0
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
        time.sleep(1)

        # must still result busy
        assert cpu_usage_monitor._get_total_cpu_usage() > 0
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
                read_bytes, write_bytes = disk_usage_monitor._get_total_disk_usage()
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
        time.sleep(1)
        _, write_bytes = disk_usage_monitor._get_total_disk_usage()
        # NOTE: due to os disk cache reading is not reliable not testing it
        assert write_bytes > 0

        # must still result busy
        assert disk_usage_monitor.is_busy is True
