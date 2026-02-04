from wifi_recover import utils


def test_prompt_consent_rejects_wrong_string() -> None:
    assert not utils.prompt_consent(
        input_func=lambda _: "nope",
        print_func=lambda *_: None,
    )


def test_prompt_consent_accepts_exact_string() -> None:
    assert utils.prompt_consent(
        input_func=lambda _: utils.CONSENT_STRING,
        print_func=lambda *_: None,
    )
