"""Tests for CompreFaceService REST client."""

from unittest.mock import patch, MagicMock
import pytest
from xface.services.compreface import CompreFaceService
from xface.core.exceptions import CompreFaceException


def test_compreface_init():
    """Verify CompreFaceService properties."""
    cf = CompreFaceService(host="http://localhost", port=8000, api_key="test-key")
    assert cf.base_url == "http://localhost:8000"
    assert "x-api-key" in cf._session.headers


@patch("requests.Session.get")
def test_compreface_list_subjects(mock_get):
    """Verify list_subjects parses CompreFace API response."""
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"subjects": ["Alice Example", "Bob Example"]}
    mock_get.return_value = mock_resp

    cf = CompreFaceService(host="http://localhost", port=8000, api_key="test-key")
    subjects = cf.list_subjects()
    assert len(subjects) == 2
    assert "Alice Example" in subjects


@patch("requests.Session.post")
def test_compreface_recognize_frame(mock_post, sample_frame):
    """Verify in-memory frame recognition sends multipart file without temp files."""
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {
        "result": [
            {
                "box": {"probability": 0.99, "x_min": 100, "y_min": 100, "x_max": 200, "y_max": 200},
                "subjects": [{"subject": "Alice Example", "similarity": 0.94}]
            }
        ]
    }
    mock_post.return_value = mock_resp

    cf = CompreFaceService(host="http://localhost", port=8000, api_key="test-key")
    results = cf.recognize_frame(sample_frame)
    assert len(results) == 1
    assert results[0]["subjects"][0]["subject"] == "Alice Example"
    assert results[0]["subjects"][0]["similarity"] == 0.94


@patch("requests.Session.delete")
def test_compreface_subject_names_are_url_encoded(mock_delete):
    """Subject names with spaces or slashes must not change the request path."""
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_delete.return_value = mock_resp

    cf = CompreFaceService(host="http://localhost", port=8000, api_key="test-key")
    cf.delete_subject("Alice/Example #1")
    called_url = mock_delete.call_args[0][0]
    assert called_url.endswith("/api/v1/recognition/subjects/Alice%2FExample%20%231")


def test_compreface_recognize_without_api_key_is_noop(sample_frame):
    """Without an API key no request is made and no faces are returned."""
    cf = CompreFaceService(host="http://localhost", port=8000, api_key="")
    assert cf.recognize_frame(sample_frame) == []
    assert cf.check_health() is False


@patch("requests.Session.post")
def test_compreface_no_face_is_not_an_error(mock_post, sample_frame):
    """CompreFace answers 400/code 28 for frames without faces; that means 'no results', not a failure."""
    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"code": 28, "message": "No face is found"}
    mock_post.return_value = mock_resp

    cf = CompreFaceService(host="http://localhost", port=8000, api_key="test-key")
    assert cf.recognize_frame(sample_frame) == []
    assert mock_post.call_count == 1  # no retries

    with pytest.raises(CompreFaceException, match="No face was found"):
        cf.add_image_to_subject("Alice Example", b"not-a-face")
