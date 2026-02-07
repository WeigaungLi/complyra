from app.core.config import Settings


def test_comma_separated_configuration_values_are_parsed() -> None:
    settings = Settings(
        cors_origins="https://app.example.com,https://admin.example.com",
        trusted_hosts="api.example.com,app.example.com",
        ingest_allowed_extensions="pdf,txt,md",
        _env_file=None,
    )

    assert settings.cors_origins == ["https://app.example.com", "https://admin.example.com"]
    assert settings.trusted_hosts == ["api.example.com", "app.example.com"]
    assert settings.ingest_allowed_extensions == ["pdf", "txt", "md"]


def test_output_policy_patterns_support_delimiter_and_json_formats() -> None:
    delimited = Settings(
        output_policy_block_patterns=r"AKIA[0-9A-Z]{16}||ASIA[0-9A-Z]{16}",
        _env_file=None,
    )
    assert delimited.output_policy_block_patterns == [r"AKIA[0-9A-Z]{16}", r"ASIA[0-9A-Z]{16}"]

    json_format = Settings(
        output_policy_block_patterns='["AKIA[0-9A-Z]{16}", "ASIA[0-9A-Z]{16}"]',
        _env_file=None,
    )
    assert json_format.output_policy_block_patterns == [r"AKIA[0-9A-Z]{16}", r"ASIA[0-9A-Z]{16}"]
