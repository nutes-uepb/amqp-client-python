from unittest.mock import Mock
import pytest


@pytest.fixture
def connection_mock():
    mock = Mock()
    yield mock
    mock.reset_mock()


@pytest.fixture
def channel_factory_mock():
    mock = Mock()
    yield mock
    mock.reset_mock()


@pytest.fixture
def channel_mock():
    mock = Mock()
    yield mock
    mock.reset_mock()
