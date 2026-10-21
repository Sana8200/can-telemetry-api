import pytest

from app.__main__ import build_config


def test_tls_config_serves_https_with_http2_first():
    config = build_config({"TLS_CERT_FILE": "server.crt", "TLS_KEY_FILE": "server.key"})
    assert config.bind == ["0.0.0.0:8443"]
    assert config.ssl_enabled
    assert config.alpn_protocols[0] == "h2"


def test_without_certificate_serves_plain_http_on_8080():
    config = build_config({})
    assert config.bind == ["0.0.0.0:8080"]
    assert not config.ssl_enabled


def test_half_a_tls_config_is_an_error():
    with pytest.raises(SystemExit):
        build_config({"TLS_CERT_FILE": "server.crt"})
