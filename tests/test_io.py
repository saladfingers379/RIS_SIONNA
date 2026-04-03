from app.io import generate_run_id


def test_generate_run_id_uses_fractional_seconds() -> None:
    run_id = generate_run_id()
    assert len(run_id.split("_")) == 3
    assert len(run_id.split("_")[-1]) == 6


def test_generate_run_id_is_unique_across_back_to_back_calls() -> None:
    first = generate_run_id()
    second = generate_run_id()
    assert first != second
