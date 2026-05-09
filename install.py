#!/usr/bin/env python3
"""
Install script for infraInstall.

This script reads install.config.json and performs file/directory operations
to install components into a parent repository. Supports both install and
uninstall operations with manifest tracking.
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Literal, TypedDict, cast


class FileElement(TypedDict):
    """Type definition for file element in config."""

    fileName: str
    sourceDirectory: str
    destination: str
    type: Literal["copy", "link"]


class DirectoryElement(TypedDict):
    """Type definition for directory element in config."""

    sourceName: str
    destinationName: str
    type: Literal["copy", "link"]


class ConfigElement(TypedDict):
    """Type definition for a config element (file or directory)."""

    file: FileElement | None
    directory: DirectoryElement | None


class InstallConfig(TypedDict):
    """Type definition for the install.config.json structure."""

    projectDirectory: str
    installDirectory: str
    manifestFile: str
    elements: list[dict[str, Any]]


class InstallationTracker:
    """Tracks installed files and directories for uninstall capability."""

    def __init__(self, manifestPath: Path) -> None:
        """
        Initialize the installation tracker.

        Args:
            manifestPath: Path where manifest file will be stored
        """
        self.manifestPath: Path = manifestPath
        self.installedItems: list[dict[str, str]] = []

    def addFile(self, sourceFile: Path, destinationFile: Path) -> None:
        """
        Record an installed file.

        Args:
            sourceFile: Path to source file
            destinationFile: Path to installed file
        """
        self.installedItems.append(
            {
                "type": "file",
                "source": str(sourceFile),
                "destination": str(destinationFile),
            }
        )

    def addDirectory(self, sourceDir: Path, destinationDir: Path) -> None:
        """
        Record an installed directory.

        Args:
            sourceDir: Path to source directory
            destinationDir: Path to installed directory
        """
        self.installedItems.append(
            {
                "type": "directory",
                "source": str(sourceDir),
                "destination": str(destinationDir),
            }
        )

    def saveManifest(self) -> None:
        """Save manifest file to disk."""
        self.manifestPath.parent.mkdir(parents=True, exist_ok=True)
        with open(self.manifestPath, "w") as f:
            json.dump({"installed": self.installedItems}, f, indent=2)
        print(f"Manifest saved to {self.manifestPath}")

    def loadManifest(self) -> bool:
        """
        Load manifest file from disk.

        Returns:
            True if manifest loaded successfully, False if file not found
        """
        if not self.manifestPath.exists():
            return False

        with open(self.manifestPath, "r") as f:
            data: dict[str, Any] = json.load(f)
            self.installedItems = cast(list[dict[str, str]], data.get("installed", []))
        return True


class Installer:
    """Main installer class for handling install/uninstall operations."""

    def __init__(self, configPath: Path) -> None:
        """
        Initialize the installer.

        Args:
            configPath: Path to install.config.json
        """
        self.configPath: Path = configPath
        self.config: InstallConfig | None = None
        self.scriptDir: Path = configPath.parent
        self.projectDir: Path | None = None
        self.tracker: InstallationTracker | None = None

    def loadConfig(self) -> bool:
        """
        Load and validate configuration file.

        Returns:
            True if config loaded successfully
        """
        if not self.configPath.exists():
            print(f"Error: Config file not found at {self.configPath}")
            return False

        try:
            with open(self.configPath, "r") as f:
                data: dict[str, Any] = json.load(f)
                self.config = cast(InstallConfig, data)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in config file: {e}")
            return False

        return True

    def resolveProjectDirectory(self) -> bool:
        """
        Resolve the project directory path.

        Returns:
            True if project directory is valid
        """
        if self.config is None:
            return False

        projectDirStr: str = self.config.get("projectDirectory", "")

        if projectDirStr == "":
            self.projectDir = self.scriptDir.parent
        else:
            self.projectDir = self.scriptDir.joinpath(projectDirStr)

        if not self.projectDir.exists():
            print(f"Error: Project directory not found at {self.projectDir}")
            return False

        return True

    def install(self) -> bool:
        """
        Perform installation of files and directories.

        Returns:
            True if installation successful
        """
        if not self.loadConfig():
            return False

        if not self.resolveProjectDirectory():
            return False

        manifestFileName: str = self.config.get("manifestFile", "")
        if manifestFileName:
            manifestPath: Path = Path.home().joinpath(manifestFileName)
        else:
            manifestPath = None

        if manifestPath:
            self.tracker = InstallationTracker(manifestPath)
        else:
            self.tracker = InstallationTracker(Path("/tmp/dummy"))

        installDir: str = self.config.get("installDirectory", "")
        if installDir:
            targetBaseDir: Path = self.projectDir.joinpath(installDir)
        else:
            targetBaseDir = self.projectDir

        targetBaseDir.mkdir(parents=True, exist_ok=True)

        elements: list[dict[str, Any]] = self.config.get("elements", [])
        for element in elements:
            if "file" in element:
                fileElem: FileElement = cast(FileElement, element["file"])
                if not self._installFile(fileElem, targetBaseDir):
                    return False
            elif "directory" in element:
                dirElem: DirectoryElement = cast(DirectoryElement, element["directory"])
                if not self._installDirectory(dirElem, targetBaseDir):
                    return False

        if manifestPath and self.tracker:
            self.tracker.saveManifest()

        print("Installation completed successfully!")
        return True

    def _installFile(self, fileElem: FileElement, baseDir: Path) -> bool:
        """
        Install a single file.

        Args:
            fileElem: File element from config
            baseDir: Base directory for installation

        Returns:
            True if file installed successfully
        """
        fileName: str = fileElem.get("fileName", "")
        sourceDir: str = fileElem.get("sourceDirectory", "")
        destination: str = fileElem.get("destination", "")
        fileType: str = fileElem.get("type", "copy")

        if not fileName:
            print("Error: fileName is required for file element")
            return False

        if sourceDir:
            sourceFile: Path = self.scriptDir.joinpath(sourceDir).joinpath(fileName)
        else:
            sourceFile = self.scriptDir.joinpath(fileName)

        if not sourceFile.exists():
            print(f"Error: Source file not found at {sourceFile}")
            return False

        if destination:
            destDir: Path = baseDir.joinpath(destination)
        else:
            destDir = baseDir

        destDir.mkdir(parents=True, exist_ok=True)
        destFile: Path = destDir.joinpath(fileName)

        try:
            if fileType == "link":
                if destFile.exists() or destFile.is_symlink():
                    destFile.unlink()
                os.symlink(sourceFile.resolve(), destFile)
                print(f"Linked: {sourceFile} -> {destFile}")
            else:  # copy
                shutil.copy2(sourceFile, destFile)
                print(f"Copied: {sourceFile} -> {destFile}")

            if self.tracker:
                self.tracker.addFile(sourceFile, destFile)

        except (OSError, IOError) as e:
            print(f"Error installing file {fileName}: {e}")
            return False

        return True

    def _installDirectory(self, dirElem: DirectoryElement, baseDir: Path) -> bool:
        """
        Install a directory.

        Args:
            dirElem: Directory element from config
            baseDir: Base directory for installation

        Returns:
            True if directory installed successfully
        """
        sourceName: str = dirElem.get("sourceName", "")
        destinationName: str = dirElem.get("destinationName", "")
        dirType: str = dirElem.get("type", "copy")

        if not sourceName:
            print("Error: sourceName is required for directory element")
            return False

        sourceDir: Path = self.scriptDir.joinpath(sourceName)

        if not sourceDir.exists():
            print(f"Error: Source directory not found at {sourceDir}")
            return False

        if destinationName:
            destDir: Path = baseDir.joinpath(destinationName)
        else:
            destDir = baseDir.joinpath(sourceName)

        try:
            if dirType == "link":
                if destDir.exists() or destDir.is_symlink():
                    if destDir.is_symlink():
                        destDir.unlink()
                    else:
                        shutil.rmtree(destDir)
                os.symlink(sourceDir.resolve(), destDir)
                print(f"Linked directory: {sourceDir} -> {destDir}")
            else:  # copy
                if destDir.exists():
                    shutil.rmtree(destDir)
                shutil.copytree(sourceDir, destDir)
                print(f"Copied directory: {sourceDir} -> {destDir}")

            if self.tracker:
                self.tracker.addDirectory(sourceDir, destDir)

        except (OSError, IOError, shutil.Error) as e:
            print(f"Error installing directory {sourceName}: {e}")
            return False

        return True

    def uninstall(self) -> bool:
        """
        Perform uninstallation based on manifest file.

        Returns:
            True if uninstallation successful
        """
        if not self.loadConfig():
            return False

        manifestFileName: str = self.config.get("manifestFile", "")
        if not manifestFileName:
            print("Error: No manifestFile defined in config")
            return False

        manifestPath: Path = Path.home().joinpath(manifestFileName)
        self.tracker = InstallationTracker(manifestPath)

        if not self.tracker.loadManifest():
            print(f"Error: Manifest file not found at {manifestPath}")
            return False

        installedItems: list[dict[str, str]] = self.tracker.installedItems
        for i in range(len(installedItems) - 1, -1, -1):
            item: dict[str, str] = installedItems[i]
            itemType: str = item.get("type", "")
            destination: str = item.get("destination", "")

            destPath: Path = Path(destination)

            try:
                if itemType == "file":
                    if destPath.exists() or destPath.is_symlink():
                        destPath.unlink()
                        print(f"Removed file: {destPath}")
                elif itemType == "directory":
                    if destPath.is_symlink():
                        destPath.unlink()
                    elif destPath.exists():
                        shutil.rmtree(destPath)
                    print(f"Removed directory: {destPath}")

            except (OSError, IOError, shutil.Error) as e:
                print(f"Error removing {destination}: {e}")
                return False

        try:
            manifestPath.unlink()
            print(f"Removed manifest: {manifestPath}")
        except OSError as e:
            print(f"Error removing manifest: {e}")
            return False

        print("Uninstallation completed successfully!")
        return True


def main() -> None:
    """Main entry point for the installer."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Install or uninstall components based on install.config.json"
    )

    parser.add_argument(
        "command",
        choices=["install", "uninstall"],
        help="Command to execute: install or uninstall",
    )

    args: argparse.Namespace = parser.parse_args()

    scriptDir: Path = Path(__file__).parent.resolve()
    configPath: Path = scriptDir.joinpath("install.config.json")

    installer: Installer = Installer(configPath)

    if args.command == "install":
        success: bool = installer.install()
    else:  # uninstall
        success = installer.uninstall()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
