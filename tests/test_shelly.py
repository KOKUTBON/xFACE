"""Tests for ShellyService relay controller and cooldown behavior."""

from unittest.mock import patch, MagicMock
import requests
from xface.services.shelly import ShellyService


def test_shelly_unconfigured():
    """Verify behavior when no Shelly URL is configured."""
    shelly = ShellyService(url=None)
    assert not shelly.trigger_relay("Alice Example")
    health = shelly.check_health()
    assert health["configured"] is False


@patch("requests.get")
def test_shelly_cooldown_behavior(mock_get):
    """Verify cooldown prevents repeated rapid triggers for the same person."""
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_get.return_value = mock_resp

    shelly = ShellyService(url="http://192.0.2.10/relay/0?turn=on", cooldown_seconds=5.0)

    # First trigger should succeed
    assert shelly.trigger_relay(subject_name="Alice") is True
    assert mock_get.call_count == 1

    # Second trigger within cooldown should be blocked
    assert shelly.trigger_relay(subject_name="Alice") is False
    assert mock_get.call_count == 1  # No additional HTTP request made

    # Forced trigger should bypass cooldown
    assert shelly.trigger_relay(subject_name="Alice", force=True) is True
    assert mock_get.call_count == 2


@patch("requests.get")
def test_shelly_network_timeout(mock_get):
    """Verify graceful handling when Shelly device is offline or times out."""
    mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")

    shelly = ShellyService(url="http://192.0.2.10/relay/0?turn=on")
    assert shelly.trigger_relay(subject_name="Bob") is False


@patch("requests.get")
def test_shelly_health_check_never_calls_trigger_url(mock_get):
    """The health check must query the read-only info endpoint, not the URL that opens the door."""
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_get.return_value = mock_resp

    for trigger_url in (
        "http://192.0.2.10/relay/0?turn=on&timer=2",
        "http://192.0.2.10/rpc/Switch.Set?id=0&on=true&toggle_after=2",
    ):
        mock_get.reset_mock()
        health = ShellyService(url=trigger_url).check_health()
        assert health["online"] is True
        mock_get.assert_called_once()
        assert mock_get.call_args[0][0] == "http://192.0.2.10/shelly"
