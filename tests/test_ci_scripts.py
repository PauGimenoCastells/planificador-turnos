from pathlib import Path


def test_ci_scripts_exist_and_contract_passes():
    """R2: Los scripts de verificación local existen."""
    repo_root = Path(__file__).resolve().parent.parent
    scripts_ci = repo_root / "scripts" / "ci"

    expected_scripts = [
        "full-suite",
        "lint",
        "security",
        "provision-e2e",
        "e2e",
    ]
    for script_name in expected_scripts:
        script_file = scripts_ci / script_name
        assert script_file.is_file(), f"Falta el script requerido: {script_name}"
