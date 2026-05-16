import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_sandbox(tmp_path: Path) -> dict[str, Path]:
    sandbox = tmp_path / "parent_repo"
    module_dir = sandbox / "infraInstall"
    home_dir = tmp_path / "home"

    module_dir.mkdir(parents=True, exist_ok=True)
    home_dir.mkdir(parents=True, exist_ok=True)

    repo_root = Path(__file__).parent.resolve()
    shutil.copy2(repo_root / "install.py", module_dir / "install.py")

    _write_text(module_dir / "source_files" / "hello.txt", "hello world\n")
    _write_text(module_dir / "source_dir" / "nested.txt", "nested payload\n")

    config = {
        "projectDirectory": "",
        "installDirectory": "installed",
        "manifestFile": ".test-install.manifest.json",
        "elements": [
            {
                "file": {
                    "fileName": "hello.txt",
                    "sourceDirectory": "source_files",
                    "destination": "files",
                    "type": "copy",
                }
            },
            {
                "file": {
                    "fileName": "install.py",
                    "sourceDirectory": "",
                    "destination": "links",
                    "type": "link",
                }
            },
            {
                "directory": {
                    "sourceName": "source_dir",
                    "destinationName": "copied_dir",
                    "type": "copy",
                }
            },
        ],
    }
    (module_dir / "install.config.json").write_text(
        json.dumps(config, indent=2), encoding="utf-8"
    )

    return {
        "sandbox": sandbox,
        "module_dir": module_dir,
        "home_dir": home_dir,
        "manifest_path": sandbox / ".test-install.manifest.json",
    }


def _run_install_command(module_dir: Path, home_dir: Path, command: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(home_dir)
    return subprocess.run(
        [sys.executable, "install.py", command],
        cwd=module_dir,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _write_config(module_dir: Path, config_data: dict[str, object]) -> None:
    (module_dir / "install.config.json").write_text(
        json.dumps(config_data, indent=2), encoding="utf-8"
    )


def test_install_creates_expected_files_links_and_manifest(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]
    manifest_path = paths["manifest_path"]

    result = _run_install_command(module_dir, home_dir, "install")

    assert result.returncode == 0, result.stdout + result.stderr

    copied_file = paths["sandbox"] / "installed" / "files" / "hello.txt"
    linked_file = paths["sandbox"] / "installed" / "links" / "install.py"
    copied_dir_file = paths["sandbox"] / "installed" / "copied_dir" / "nested.txt"

    assert copied_file.exists()
    assert copied_file.read_text(encoding="utf-8") == "hello world\n"

    assert linked_file.is_symlink()
    assert linked_file.resolve() == (module_dir / "install.py").resolve()

    assert copied_dir_file.exists()
    assert copied_dir_file.read_text(encoding="utf-8") == "nested payload\n"

    assert manifest_path.exists()
    assert not (home_dir / ".test-install.manifest.json").exists()
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "installed" in manifest_data
    assert len(manifest_data["installed"]) == 3


def test_install_overwrites_existing_manifest_file(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]
    manifest_path = paths["manifest_path"]

    manifest_path.write_text(
        json.dumps({"installed": [{"destination": "stale"}], "oldKey": True}, indent=2),
        encoding="utf-8",
    )

    result = _run_install_command(module_dir, home_dir, "install")
    assert result.returncode == 0, result.stdout + result.stderr

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "installed" in manifest_data
    assert len(manifest_data["installed"]) == 3
    assert "oldKey" not in manifest_data


def test_install_is_idempotent_with_same_config(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]
    sandbox = paths["sandbox"]
    manifest_path = paths["manifest_path"]

    first_result = _run_install_command(module_dir, home_dir, "install")
    assert first_result.returncode == 0, first_result.stdout + first_result.stderr

    second_result = _run_install_command(module_dir, home_dir, "install")
    assert second_result.returncode == 0, second_result.stdout + second_result.stderr

    copied_file = sandbox / "installed" / "files" / "hello.txt"
    linked_file = sandbox / "installed" / "links" / "install.py"
    copied_dir = sandbox / "installed" / "copied_dir"
    assert copied_file.exists()
    assert copied_file.read_text(encoding="utf-8") == "hello world\n"
    assert linked_file.is_symlink()
    assert copied_dir.exists()

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    installed_entries = manifest_data.get("installed", [])
    assert len(installed_entries) == 3
    destinations = [entry.get("destination", "") for entry in installed_entries]
    assert len(destinations) == len(set(destinations))


def test_install_allows_duplicate_targets_and_later_element_wins(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]
    sandbox = paths["sandbox"]
    manifest_path = paths["manifest_path"]

    _write_text(module_dir / "source_alt" / "hello.txt", "alt content\n")

    config_path = module_dir / "install.config.json"
    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    config_data["elements"] = [
        {
            "file": {
                "fileName": "hello.txt",
                "sourceDirectory": "source_files",
                "destination": "files",
                "type": "copy",
            }
        },
        {
            "file": {
                "fileName": "hello.txt",
                "sourceDirectory": "source_alt",
                "destination": "files",
                "type": "copy",
            }
        },
    ]
    _write_config(module_dir, config_data)

    result = _run_install_command(module_dir, home_dir, "install")
    assert result.returncode == 0, result.stdout + result.stderr

    copied_file = sandbox / "installed" / "files" / "hello.txt"
    assert copied_file.exists()
    assert copied_file.read_text(encoding="utf-8") == "alt content\n"

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    installed_entries = manifest_data.get("installed", [])
    assert len(installed_entries) == 2
    assert installed_entries[0]["destination"] == installed_entries[1]["destination"]


def test_install_ignores_unknown_extra_keys_in_elements(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]
    sandbox = paths["sandbox"]
    manifest_path = paths["manifest_path"]

    config_path = module_dir / "install.config.json"
    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    config_data["elements"][0]["file"]["unexpectedFileKey"] = "ignored"
    config_data["elements"][2]["directory"]["unexpectedDirectoryKey"] = {
        "nested": True
    }
    _write_config(module_dir, config_data)

    result = _run_install_command(module_dir, home_dir, "install")
    assert result.returncode == 0, result.stdout + result.stderr

    copied_file = sandbox / "installed" / "files" / "hello.txt"
    linked_file = sandbox / "installed" / "links" / "install.py"
    copied_dir = sandbox / "installed" / "copied_dir"
    assert copied_file.exists()
    assert linked_file.exists()
    assert copied_dir.exists()
    assert manifest_path.exists()


def test_uninstall_removes_installed_items_and_manifest(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]
    manifest_path = paths["manifest_path"]

    install_result = _run_install_command(module_dir, home_dir, "install")
    assert install_result.returncode == 0, install_result.stdout + install_result.stderr

    uninstall_result = _run_install_command(module_dir, home_dir, "uninstall")
    assert uninstall_result.returncode == 0, uninstall_result.stdout + uninstall_result.stderr

    copied_file = paths["sandbox"] / "installed" / "files" / "hello.txt"
    linked_file = paths["sandbox"] / "installed" / "links" / "install.py"
    copied_dir = paths["sandbox"] / "installed" / "copied_dir"

    assert not copied_file.exists()
    assert not linked_file.exists()
    assert not copied_dir.exists()
    assert not manifest_path.exists()


def test_uninstall_second_run_fails_after_successful_uninstall(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]
    sandbox = paths["sandbox"]
    manifest_path = paths["manifest_path"]

    install_result = _run_install_command(module_dir, home_dir, "install")
    assert install_result.returncode == 0, install_result.stdout + install_result.stderr

    first_uninstall = _run_install_command(module_dir, home_dir, "uninstall")
    assert first_uninstall.returncode == 0, first_uninstall.stdout + first_uninstall.stderr

    second_uninstall = _run_install_command(module_dir, home_dir, "uninstall")
    assert second_uninstall.returncode != 0
    combined_output = second_uninstall.stdout + second_uninstall.stderr
    assert "Manifest file not found" in combined_output

    copied_file = sandbox / "installed" / "files" / "hello.txt"
    linked_file = sandbox / "installed" / "links" / "install.py"
    copied_dir = sandbox / "installed" / "copied_dir"
    assert not copied_file.exists()
    assert not linked_file.exists()
    assert not copied_dir.exists()
    assert not manifest_path.exists()


def test_uninstall_fails_when_manifest_missing(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]

    result = _run_install_command(module_dir, home_dir, "uninstall")

    assert result.returncode != 0
    combined_output = result.stdout + result.stderr
    assert "Manifest file not found" in combined_output


def test_uninstall_fails_when_manifest_is_malformed(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]
    manifest_path = paths["manifest_path"]

    install_result = _run_install_command(module_dir, home_dir, "install")
    assert install_result.returncode == 0, install_result.stdout + install_result.stderr

    manifest_path.write_text("{not valid json", encoding="utf-8")

    result = _run_install_command(module_dir, home_dir, "uninstall")

    assert result.returncode != 0
    combined_output = result.stdout + result.stderr
    assert "JSONDecodeError" in combined_output or "Expecting" in combined_output


def test_uninstall_continues_when_manifest_destination_is_missing(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]
    sandbox = paths["sandbox"]
    manifest_path = paths["manifest_path"]

    install_result = _run_install_command(module_dir, home_dir, "install")
    assert install_result.returncode == 0, install_result.stdout + install_result.stderr

    missing_before_uninstall = sandbox / "installed" / "files" / "hello.txt"
    missing_before_uninstall.unlink()
    assert not missing_before_uninstall.exists()

    uninstall_result = _run_install_command(module_dir, home_dir, "uninstall")
    assert (
        uninstall_result.returncode == 0
    ), uninstall_result.stdout + uninstall_result.stderr

    linked_file = sandbox / "installed" / "links" / "install.py"
    copied_dir = sandbox / "installed" / "copied_dir"
    assert not linked_file.exists()
    assert not copied_dir.exists()
    assert not manifest_path.exists()


def test_uninstall_fails_when_manifest_path_mismatches_config_change(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]
    sandbox = paths["sandbox"]
    original_manifest = paths["manifest_path"]

    install_result = _run_install_command(module_dir, home_dir, "install")
    assert install_result.returncode == 0, install_result.stdout + install_result.stderr

    config_path = module_dir / "install.config.json"
    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    config_data["manifestFile"] = ".different-install.manifest.json"
    _write_config(module_dir, config_data)

    uninstall_result = _run_install_command(module_dir, home_dir, "uninstall")

    assert uninstall_result.returncode != 0
    combined_output = uninstall_result.stdout + uninstall_result.stderr
    assert "Manifest file not found" in combined_output

    copied_file = sandbox / "installed" / "files" / "hello.txt"
    linked_file = sandbox / "installed" / "links" / "install.py"
    copied_dir = sandbox / "installed" / "copied_dir"
    assert copied_file.exists()
    assert linked_file.exists()
    assert copied_dir.exists()
    assert original_manifest.exists()


def test_install_uses_non_empty_project_directory_for_outputs_and_manifest(
    tmp_path: Path,
) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]

    custom_project_dir = module_dir / "custom_project"
    custom_project_dir.mkdir(parents=True, exist_ok=True)

    config_path = module_dir / "install.config.json"
    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    config_data["projectDirectory"] = "custom_project"
    config_path.write_text(json.dumps(config_data, indent=2), encoding="utf-8")

    result = _run_install_command(module_dir, home_dir, "install")
    assert result.returncode == 0, result.stdout + result.stderr

    copied_file = custom_project_dir / "installed" / "files" / "hello.txt"
    manifest_path = custom_project_dir / ".test-install.manifest.json"

    assert copied_file.exists()
    assert copied_file.read_text(encoding="utf-8") == "hello world\n"
    assert manifest_path.exists()
    assert not (home_dir / ".test-install.manifest.json").exists()


def test_install_directory_blank_defaults_to_project_directory(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]

    config_path = module_dir / "install.config.json"
    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    config_data["installDirectory"] = ""
    config_data["elements"] = [
        {
            "file": {
                "fileName": "hello.txt",
                "sourceDirectory": "source_files",
                "destination": "",
                "type": "copy",
            }
        }
    ]
    config_path.write_text(json.dumps(config_data, indent=2), encoding="utf-8")

    result = _run_install_command(module_dir, home_dir, "install")
    assert result.returncode == 0, result.stdout + result.stderr

    copied_file = paths["sandbox"] / "hello.txt"
    assert copied_file.exists()
    assert copied_file.read_text(encoding="utf-8") == "hello world\n"


def test_install_exits_when_elements_array_is_empty(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]

    config_path = module_dir / "install.config.json"
    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    config_data["elements"] = []
    config_path.write_text(json.dumps(config_data, indent=2), encoding="utf-8")

    result = _run_install_command(module_dir, home_dir, "install")

    assert result.returncode != 0


def test_install_exits_for_invalid_element_type(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]

    config_path = module_dir / "install.config.json"
    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    config_data["elements"] = [{"invalid": {"anything": "value"}}]
    config_path.write_text(json.dumps(config_data, indent=2), encoding="utf-8")

    result = _run_install_command(module_dir, home_dir, "install")

    assert result.returncode != 0


@pytest.mark.parametrize(
    "file_element",
    [
        {"sourceDirectory": "source_files", "destination": "", "type": "copy"},
        {"fileName": "", "sourceDirectory": "source_files", "destination": "", "type": "copy"},
        {"fileName": "hello.txt", "destination": "", "type": "copy"},
        {"fileName": "hello.txt", "sourceDirectory": "source_files", "type": "copy"},
        {"fileName": "hello.txt", "sourceDirectory": "source_files", "destination": ""},
        {
            "fileName": "hello.txt",
            "sourceDirectory": "source_files",
            "destination": "",
            "type": "invalid",
        },
    ],
)
def test_install_exits_for_invalid_file_element_shape_or_values(
    tmp_path: Path, file_element: dict[str, str]
) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]

    config_path = module_dir / "install.config.json"
    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    config_data["elements"] = [{"file": file_element}]
    _write_config(module_dir, config_data)

    result = _run_install_command(module_dir, home_dir, "install")

    assert result.returncode != 0


@pytest.mark.parametrize(
    "dir_element",
    [
        {},
        {"destinationName": "copied_dir", "type": "copy"},
        {"sourceName": "", "destinationName": "copied_dir", "type": "copy"},
        {"sourceName": "source_dir", "type": "copy"},
        {"sourceName": "source_dir", "destinationName": "copied_dir"},
        {"sourceName": "source_dir", "destinationName": "copied_dir", "type": "invalid"},
    ],
)
def test_install_exits_for_invalid_directory_element_shape_or_values(
    tmp_path: Path, dir_element: dict[str, str]
) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]

    config_path = module_dir / "install.config.json"
    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    config_data["elements"] = [{"directory": dir_element}]
    _write_config(module_dir, config_data)

    result = _run_install_command(module_dir, home_dir, "install")

    assert result.returncode != 0


def test_install_directory_empty_destination_name_uses_source_name(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]

    config_path = module_dir / "install.config.json"
    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    config_data["elements"] = [
        {
            "directory": {
                "sourceName": "source_dir",
                "destinationName": "",
                "type": "copy",
            }
        }
    ]
    _write_config(module_dir, config_data)

    result = _run_install_command(module_dir, home_dir, "install")
    assert result.returncode == 0, result.stdout + result.stderr

    copied_dir_file = paths["sandbox"] / "installed" / "source_dir" / "nested.txt"
    assert copied_dir_file.exists()
    assert copied_dir_file.read_text(encoding="utf-8") == "nested payload\n"


def test_install_fails_when_config_file_missing(tmp_path: Path) -> None:
    sandbox = tmp_path / "parent_repo"
    module_dir = sandbox / "infraInstall"
    home_dir = tmp_path / "home"

    module_dir.mkdir(parents=True, exist_ok=True)
    home_dir.mkdir(parents=True, exist_ok=True)

    repo_root = Path(__file__).parent.resolve()
    shutil.copy2(repo_root / "install.py", module_dir / "install.py")

    result = _run_install_command(module_dir, home_dir, "install")

    assert result.returncode != 0
    assert "install.config.json" in result.stdout or "install.config.json" in result.stderr


def test_install_fails_when_config_json_is_invalid(tmp_path: Path) -> None:
    sandbox = tmp_path / "parent_repo"
    module_dir = sandbox / "infraInstall"
    home_dir = tmp_path / "home"

    module_dir.mkdir(parents=True, exist_ok=True)
    home_dir.mkdir(parents=True, exist_ok=True)

    repo_root = Path(__file__).parent.resolve()
    shutil.copy2(repo_root / "install.py", module_dir / "install.py")

    invalid_json = "{ this is not valid json }"
    (module_dir / "install.config.json").write_text(invalid_json, encoding="utf-8")

    result = _run_install_command(module_dir, home_dir, "install")

    assert result.returncode != 0
    assert "JSON" in result.stdout or "JSON" in result.stderr or "json" in result.stdout or "json" in result.stderr


@pytest.mark.parametrize(
    "missing_key",
    ["projectDirectory", "installDirectory", "manifestFile", "elements"],
)
def test_install_fails_when_required_top_level_key_is_missing(
    tmp_path: Path, missing_key: str
) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]

    config_path = module_dir / "install.config.json"
    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    del config_data[missing_key]
    _write_config(module_dir, config_data)

    result = _run_install_command(module_dir, home_dir, "install")

    assert result.returncode != 0


@pytest.mark.parametrize(
    "invalid_config",
    [
        {"projectDirectory": 123, "installDirectory": "", "manifestFile": "", "elements": []},
        {"projectDirectory": "", "installDirectory": 456, "manifestFile": "", "elements": []},
        {"projectDirectory": "", "installDirectory": "", "manifestFile": 789, "elements": []},
        {"projectDirectory": "", "installDirectory": "", "manifestFile": "", "elements": {}},
        {"projectDirectory": ["not", "a", "string"], "installDirectory": "", "manifestFile": "", "elements": []},
    ],
)
def test_install_fails_for_invalid_top_level_value_types(
    tmp_path: Path, invalid_config: dict
) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]

    _write_config(module_dir, invalid_config)

    result = _run_install_command(module_dir, home_dir, "install")

    assert result.returncode != 0


def test_install_fails_when_manifest_file_is_empty(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]

    config_path = module_dir / "install.config.json"
    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    config_data["manifestFile"] = ""
    _write_config(module_dir, config_data)

    result = _run_install_command(module_dir, home_dir, "install")

    assert result.returncode != 0


def test_install_fails_when_project_directory_does_not_exist(tmp_path: Path) -> None:
    sandbox = tmp_path / "parent_repo"
    module_dir = sandbox / "infraInstall"
    home_dir = tmp_path / "home"

    module_dir.mkdir(parents=True, exist_ok=True)
    home_dir.mkdir(parents=True, exist_ok=True)

    repo_root = Path(__file__).parent.resolve()
    shutil.copy2(repo_root / "install.py", module_dir / "install.py")

    _write_text(module_dir / "source_files" / "hello.txt", "hello world\n")

    config = {
        "projectDirectory": "nonexistent_project",
        "installDirectory": "",
        "manifestFile": "",
        "elements": [
            {
                "file": {
                    "fileName": "hello.txt",
                    "sourceDirectory": "source_files",
                    "destination": "",
                    "type": "copy",
                }
            }
        ],
    }
    (module_dir / "install.config.json").write_text(
        json.dumps(config, indent=2), encoding="utf-8"
    )

    result = _run_install_command(module_dir, home_dir, "install")

    assert result.returncode != 0


def test_install_fails_with_path_traversal_in_project_directory(tmp_path: Path) -> None:
    sandbox = tmp_path / "parent_repo"
    module_dir = sandbox / "infraInstall"
    home_dir = tmp_path / "home"

    module_dir.mkdir(parents=True, exist_ok=True)
    home_dir.mkdir(parents=True, exist_ok=True)

    repo_root = Path(__file__).parent.resolve()
    shutil.copy2(repo_root / "install.py", module_dir / "install.py")

    _write_text(module_dir / "source_files" / "hello.txt", "hello world\n")

    config = {
        "projectDirectory": "../somewhere_else",
        "installDirectory": "installed",
        "manifestFile": ".test-install.manifest.json",
        "elements": [
            {
                "file": {
                    "fileName": "hello.txt",
                    "sourceDirectory": "source_files",
                    "destination": "",
                    "type": "copy",
                }
            }
        ],
    }
    (module_dir / "install.config.json").write_text(
        json.dumps(config, indent=2), encoding="utf-8"
    )

    result = _run_install_command(module_dir, home_dir, "install")

    assert result.returncode != 0


def test_install_fails_when_install_directory_is_absolute(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]

    config_path = module_dir / "install.config.json"
    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    config_data["installDirectory"] = "/tmp/absolute-install-dir"
    _write_config(module_dir, config_data)

    result = _run_install_command(module_dir, home_dir, "install")

    assert result.returncode != 0


def test_install_fails_with_path_traversal_in_install_directory(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]

    config_path = module_dir / "install.config.json"
    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    config_data["installDirectory"] = "../outside"
    _write_config(module_dir, config_data)

    result = _run_install_command(module_dir, home_dir, "install")

    assert result.returncode != 0


def test_install_fails_when_manifest_file_is_absolute(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]

    config_path = module_dir / "install.config.json"
    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    config_data["manifestFile"] = "/tmp/absolute-manifest.json"
    _write_config(module_dir, config_data)

    result = _run_install_command(module_dir, home_dir, "install")

    assert result.returncode != 0


def test_install_fails_with_path_traversal_in_manifest_file(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]

    config_path = module_dir / "install.config.json"
    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    config_data["manifestFile"] = "../outside.manifest.json"
    _write_config(module_dir, config_data)

    result = _run_install_command(module_dir, home_dir, "install")

    assert result.returncode != 0


def test_install_fails_when_source_file_missing(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]

    config_path = module_dir / "install.config.json"
    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    # Modify config to reference a non-existent source file
    config_data["elements"][0]["file"]["fileName"] = "nonexistent.txt"
    _write_config(module_dir, config_data)

    result = _run_install_command(module_dir, home_dir, "install")

    assert result.returncode != 0


def test_install_fails_when_source_directory_missing(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]

    config_path = module_dir / "install.config.json"
    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    # Modify config to reference a non-existent source directory (directory element is at index 2)
    config_data["elements"][2]["directory"]["sourceName"] = "nonexistent_dir"
    _write_config(module_dir, config_data)

    result = _run_install_command(module_dir, home_dir, "install")

    assert result.returncode != 0


def test_install_overwrites_existing_file_on_copy(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]
    sandbox = paths["sandbox"]

    # First install - creates the file
    result = _run_install_command(module_dir, home_dir, "install")
    assert result.returncode == 0, result.stdout + result.stderr

    # Verify file was copied
    copied_file = sandbox / "installed" / "files" / "hello.txt"
    assert copied_file.exists()
    assert copied_file.read_text(encoding="utf-8") == "hello world\n"

    # Modify the copied file to have different content
    copied_file.write_text("modified content\n", encoding="utf-8")
    assert copied_file.read_text(encoding="utf-8") == "modified content\n"

    # Run install again
    result = _run_install_command(module_dir, home_dir, "install")
    assert result.returncode == 0, result.stdout + result.stderr

    # Verify file was overwritten with original content
    assert copied_file.exists()
    assert copied_file.read_text(encoding="utf-8") == "hello world\n"


def test_install_replaces_existing_directory_on_copy(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]
    sandbox = paths["sandbox"]

    # First install - creates the directory
    result = _run_install_command(module_dir, home_dir, "install")
    assert result.returncode == 0, result.stdout + result.stderr

    # Verify directory was copied
    copied_dir = sandbox / "installed" / "copied_dir"
    assert copied_dir.is_dir()
    nested_file = copied_dir / "nested.txt"
    assert nested_file.exists()
    assert nested_file.read_text(encoding="utf-8") == "nested payload\n"

    # Create an extra file in the copied directory
    extra_file = copied_dir / "extra.txt"
    extra_file.write_text("extra content\n", encoding="utf-8")
    assert extra_file.exists()

    # Run install again
    result = _run_install_command(module_dir, home_dir, "install")
    assert result.returncode == 0, result.stdout + result.stderr

    # Verify directory was replaced (extra file should be gone)
    assert copied_dir.is_dir()
    assert nested_file.exists()
    assert not extra_file.exists()


def test_install_replaces_existing_file_link(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]
    sandbox = paths["sandbox"]

    # First install - creates the link
    result = _run_install_command(module_dir, home_dir, "install")
    assert result.returncode == 0, result.stdout + result.stderr

    # Verify link was created
    linked_file = sandbox / "installed" / "links" / "install.py"
    assert linked_file.is_symlink()
    original_target = linked_file.resolve()

    # Replace the link with a regular file
    linked_file.unlink()
    linked_file.write_text("regular file content\n", encoding="utf-8")
    assert linked_file.is_file()
    assert not linked_file.is_symlink()

    # Run install again
    result = _run_install_command(module_dir, home_dir, "install")
    assert result.returncode == 0, result.stdout + result.stderr

    # Verify link was recreated
    assert linked_file.is_symlink()
    assert linked_file.resolve() == original_target


def test_install_replaces_existing_directory_link(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]
    sandbox = paths["sandbox"]

    # Modify config to use link for directory instead of copy
    config_path = module_dir / "install.config.json"
    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    config_data["elements"][2]["directory"]["type"] = "link"
    _write_config(module_dir, config_data)

    # First install - creates the link
    result = _run_install_command(module_dir, home_dir, "install")
    assert result.returncode == 0, result.stdout + result.stderr

    # Verify link was created
    linked_dir = sandbox / "installed" / "copied_dir"
    assert linked_dir.is_symlink()
    original_target = linked_dir.resolve()

    # Replace the link with a regular directory
    linked_dir.unlink()
    linked_dir.mkdir()
    fake_file = linked_dir / "fake.txt"
    fake_file.write_text("fake content\n", encoding="utf-8")
    assert linked_dir.is_dir()
    assert not linked_dir.is_symlink()

    # Run install again
    result = _run_install_command(module_dir, home_dir, "install")
    assert result.returncode == 0, result.stdout + result.stderr

    # Verify link was recreated
    assert linked_dir.is_symlink()
    assert linked_dir.resolve() == original_target
    assert not fake_file.exists()


def test_install_fails_when_file_symlink_creation_fails_permission_denied(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]
    sandbox = paths["sandbox"]

    # Modify config to use link for file element
    config_path = module_dir / "install.config.json"
    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    config_data["elements"][0]["file"]["type"] = "link"
    _write_config(module_dir, config_data)

    # Make the destination directory read-only to simulate permission denied
    installed_dir = sandbox / "installed"
    installed_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(installed_dir, 0o444)

    try:
        result = _run_install_command(module_dir, home_dir, "install")
        assert result.returncode != 0
        assert "Error" in result.stdout or "Error" in result.stderr
    finally:
        # Restore permissions for cleanup
        os.chmod(installed_dir, 0o755)


def test_install_fails_when_directory_symlink_creation_fails_permission_denied(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]
    sandbox = paths["sandbox"]

    # Modify config to use link for directory element
    config_path = module_dir / "install.config.json"
    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    config_data["elements"][2]["directory"]["type"] = "link"
    _write_config(module_dir, config_data)

    # Make the destination directory read-only to simulate permission denied
    installed_dir = sandbox / "installed"
    installed_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(installed_dir, 0o444)

    try:
        result = _run_install_command(module_dir, home_dir, "install")
        assert result.returncode != 0
        assert "Error" in result.stdout or "Error" in result.stderr
    finally:
        # Restore permissions for cleanup
        os.chmod(installed_dir, 0o755)


def test_install_fails_when_destination_parent_cannot_be_created(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]
    sandbox = paths["sandbox"]

    config_path = module_dir / "install.config.json"
    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    config_data["projectDirectory"] = "custom_project"
    config_data["installDirectory"] = "installed/subdir"
    _write_config(module_dir, config_data)

    custom_project = sandbox / "infraInstall" / "custom_project"
    custom_project.mkdir(parents=True, exist_ok=True)
    os.chmod(custom_project, 0o555)

    try:
        result = _run_install_command(module_dir, home_dir, "install")

        assert result.returncode != 0
        combined_output = result.stdout + result.stderr
        assert "Permission denied" in combined_output or "Errno" in combined_output
    finally:
        os.chmod(custom_project, 0o755)


def test_install_fails_when_manifest_write_fails_and_keeps_installed_items(
    tmp_path: Path,
) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]
    sandbox = paths["sandbox"]

    config_path = module_dir / "install.config.json"
    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    config_data["projectDirectory"] = "custom_project"
    config_data["installDirectory"] = "installed"
    config_data["manifestFile"] = "restricted/.test-install.manifest.json"
    _write_config(module_dir, config_data)

    custom_project = sandbox / "infraInstall" / "custom_project"
    custom_project.mkdir(parents=True, exist_ok=True)
    restricted_dir = custom_project / "restricted"
    restricted_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(restricted_dir, 0o555)

    try:
        result = _run_install_command(module_dir, home_dir, "install")

        assert result.returncode != 0
        copied_file = custom_project / "installed" / "files" / "hello.txt"
        linked_file = custom_project / "installed" / "links" / "install.py"
        copied_dir = custom_project / "installed" / "copied_dir"
        assert copied_file.exists()
        assert linked_file.exists()
        assert copied_dir.exists()
        combined_output = result.stdout + result.stderr
        assert "Permission denied" in combined_output or "Errno" in combined_output
    finally:
        os.chmod(restricted_dir, 0o755)


def test_partial_install_failure_keeps_previously_installed_items(tmp_path: Path) -> None:
    paths = _build_sandbox(tmp_path)
    module_dir = paths["module_dir"]
    home_dir = paths["home_dir"]
    sandbox = paths["sandbox"]

    # Create a config with multiple elements, where second one fails
    config = {
        "projectDirectory": "",
        "installDirectory": "installed",
        "manifestFile": ".test-install.manifest.json",
        "elements": [
            {
                "file": {
                    "fileName": "hello.txt",
                    "sourceDirectory": "source_files",
                    "destination": "files",
                    "type": "copy",
                }
            },
            {
                "file": {
                    "fileName": "nonexistent.txt",
                    "sourceDirectory": "source_files",
                    "destination": "files",
                    "type": "copy",
                }
            },
            {
                "file": {
                    "fileName": "install.py",
                    "sourceDirectory": "",
                    "destination": "links",
                    "type": "link",
                }
            },
        ],
    }
    _write_config(module_dir, config)

    # Run install - should fail on second element
    result = _run_install_command(module_dir, home_dir, "install")

    # Should fail
    assert result.returncode != 0

    # First element should be installed
    copied_file = sandbox / "installed" / "files" / "hello.txt"
    assert copied_file.exists()
    assert copied_file.read_text(encoding="utf-8") == "hello world\n"

    # Third element should NOT be installed (stopped after failure)
    linked_file = sandbox / "installed" / "links" / "install.py"
    assert not linked_file.exists()
