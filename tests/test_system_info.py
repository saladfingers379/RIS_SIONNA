from app.utils.system import _repo_runtime_warnings


def test_repo_runtime_warnings_for_python_312() -> None:
    warnings = _repo_runtime_warnings(python_info=(3, 12, 0), numpy_version="1.26.4")
    assert warnings
    assert "Python 3.12 detected." in warnings[0]
    assert "Sionna 0.19.2" in warnings[0]


def test_repo_runtime_warnings_for_numpy_2() -> None:
    warnings = _repo_runtime_warnings(python_info=(3, 11, 9), numpy_version="2.1.0")
    assert warnings
    assert "NumPy 2.x detected." in warnings[0]
    assert "NumPy 1.26.4" in warnings[0]


def test_repo_runtime_warnings_empty_for_supported_runtime() -> None:
    warnings = _repo_runtime_warnings(python_info=(3, 11, 9), numpy_version="1.26.4")
    assert warnings == []
