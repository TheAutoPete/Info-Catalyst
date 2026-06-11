from services.openai_client import _connection_error_message


def test_connection_error_message_mentions_proxy_when_enabled(monkeypatch):
    monkeypatch.setattr("services.openai_client.OPENAI_USE_SYSTEM_PROXY", True)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9999")

    message = _connection_error_message(RuntimeError("connection refused"))

    assert "Could not connect to the OpenAI API" in message
    assert "HTTPS_PROXY" in message
    assert "OPENAI_USE_SYSTEM_PROXY=false" in message


def test_connection_error_message_hides_proxy_hint_when_disabled(monkeypatch):
    monkeypatch.setattr("services.openai_client.OPENAI_USE_SYSTEM_PROXY", False)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9999")

    message = _connection_error_message(RuntimeError("connection refused"))

    assert "Could not connect to the OpenAI API" in message
    assert "Detected proxy environment variables" not in message
