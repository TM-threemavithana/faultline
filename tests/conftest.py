"""
Shared pytest fixtures and configuration.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_disk_usage_ok(mocker):
    """Patch psutil.disk_usage to return a healthy (50%) usage."""
    usage = MagicMock()
    usage.total = 100 * 1024**3
    usage.used = 50 * 1024**3
    usage.free = 50 * 1024**3
    usage.percent = 50.0
    mocker.patch("psutil.disk_usage", return_value=usage)
    return usage


@pytest.fixture
def mock_disk_usage_critical(mocker):
    """Patch psutil.disk_usage to return a critical (92%) usage."""
    usage = MagicMock()
    usage.total = 100 * 1024**3
    usage.used = 92 * 1024**3
    usage.free = 8 * 1024**3
    usage.percent = 92.0
    mocker.patch("psutil.disk_usage", return_value=usage)
    return usage


@pytest.fixture
def mock_cpu_ok(mocker):
    mocker.patch("psutil.cpu_percent", return_value=30.0)
    mocker.patch("psutil.cpu_count", return_value=4)
    return 30.0


@pytest.fixture
def mock_cpu_warning(mocker):
    mocker.patch("psutil.cpu_percent", return_value=90.0)
    mocker.patch("psutil.cpu_count", return_value=4)
    return 90.0


@pytest.fixture
def mock_memory_ok(mocker):
    vm = MagicMock()
    vm.total = 16 * 1024**3
    vm.available = 8 * 1024**3
    vm.percent = 50.0
    swap = MagicMock()
    swap.total = 4 * 1024**3
    swap.percent = 5.0
    mocker.patch("psutil.virtual_memory", return_value=vm)
    mocker.patch("psutil.swap_memory", return_value=swap)
    return vm


@pytest.fixture
def mock_memory_critical(mocker):
    vm = MagicMock()
    vm.total = 16 * 1024**3
    vm.available = 500 * 1024**2
    vm.percent = 97.0
    swap = MagicMock()
    swap.total = 4 * 1024**3
    swap.percent = 80.0
    mocker.patch("psutil.virtual_memory", return_value=vm)
    mocker.patch("psutil.swap_memory", return_value=swap)
    return vm

