import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


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
        "manifest_path": home_dir / ".test-install.manifest.json",
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
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "installed" in manifest_data
    assert len(manifest_data["installed"]) == 3


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
