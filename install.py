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
        self.installedItems: list[dict[str, Any]] = []

    def addFile(
        self,
        sourceFile: str,
        destinationFile: str,
        destinationBase: Literal["scriptDir", "projectDir"],
    ) -> None:
        """
        Record an installed file.

        Args:
            sourceFile: Source file path stored in manifest
            destinationFile: Destination file path stored in manifest
            destinationBase: Base path used to resolve destination during uninstall
        """
        self.installedItems.append(
            {
                "type": "file",
                "source": sourceFile,
                "destination": destinationFile,
                "destinationBase": destinationBase,
            }
        )

    def addDirectory(
        self,
        sourceDir: str,
        destinationDir: str,
        destinationBase: Literal["scriptDir", "projectDir"],
    ) -> None:
        """
        Record an installed directory.

        Args:
            sourceDir: Source directory path stored in manifest
            destinationDir: Destination directory path stored in manifest
            destinationBase: Base path used to resolve destination during uninstall
        """
        self.installedItems.append(
            {
                "type": "directory",
                "source": sourceDir,
                "destination": destinationDir,
                "destinationBase": destinationBase,
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

        try:
            with open(self.manifestPath, "r") as f:
                data: Any = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Manifest JSON parse error: {e}") from e
        except OSError as e:
            raise ValueError(f"Unable to read manifest file: {e}") from e

        if not isinstance(data, dict):
            raise ValueError("Manifest content must be a JSON object")

        installedItems: Any = data.get("installed", [])
        if not isinstance(installedItems, list):
            raise ValueError("Manifest field 'installed' must be an array")

        self.installedItems = cast(list[dict[str, Any]], installedItems)
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
                data: Any = json.load(f)
                if not isinstance(data, dict):
                    print("Error: Config must be a JSON object")
                    return False
                self.config = cast(InstallConfig, data)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in config file: {e}")
            return False
        except OSError as e:
            print(f"Error: Unable to read config file: {e}")
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

        projectDirStr: str = self.config["projectDirectory"]

        if projectDirStr == "":
            self.projectDir = self.scriptDir.parent
        else:
            projectPath: Path = Path(projectDirStr)
            if projectPath.is_absolute():
                print("Error: projectDirectory must be a relative path")
                return False
            if ".." in projectPath.parts:
                print("Error: projectDirectory must not contain path traversal '..'")
                return False

            self.projectDir = self.scriptDir.joinpath(projectPath)

        if not self.projectDir.exists():
            print(f"Error: Project directory not found at {self.projectDir}")
            return False

        return True

    @staticmethod
    def validateConfig(configData: InstallConfig) -> None:
        """
        Validate configuration structure and values required for installation.

        Args:
            configData: Parsed install configuration

        Raises:
            ValueError: If configuration is invalid
        """
        requiredTopLevelKeys: tuple[str, ...] = (
            "projectDirectory",
            "installDirectory",
            "manifestFile",
            "elements",
        )
        missingKeys: list[str] = [
            key for key in requiredTopLevelKeys if key not in configData
        ]
        if missingKeys:
            missingKeysDisplay: str = ", ".join(missingKeys)
            raise ValueError(f"config is missing required key(s): {missingKeysDisplay}")

        projectDirectory: Any = configData["projectDirectory"]
        installDirectory: Any = configData["installDirectory"]
        manifestFile: Any = configData["manifestFile"]
        elementsValue: Any = configData["elements"]

        if not isinstance(projectDirectory, str):
            raise ValueError("'projectDirectory' must be a string")
        if not isinstance(installDirectory, str):
            raise ValueError("'installDirectory' must be a string")
        if not isinstance(manifestFile, str):
            raise ValueError("'manifestFile' must be a string")
        if manifestFile == "":
            raise ValueError("'manifestFile' must be a non-empty string")
        if not isinstance(elementsValue, list):
            raise ValueError("'elements' must be an array")

        if installDirectory != "":
            installDirectoryPath: Path = Path(installDirectory)
            if installDirectoryPath.is_absolute():
                raise ValueError("'installDirectory' must be a relative path")
            if ".." in installDirectoryPath.parts:
                raise ValueError(
                    "'installDirectory' must not contain path traversal '..'"
                )

        manifestFilePath: Path = Path(manifestFile)
        if manifestFilePath.is_absolute():
            raise ValueError("'manifestFile' must be a relative path")
        if ".." in manifestFilePath.parts:
            raise ValueError("'manifestFile' must not contain path traversal '..'")

        elements: list[dict[str, Any]] = cast(list[dict[str, Any]], elementsValue)
        if len(elements) == 0:
            raise ValueError("elements array is empty; nothing to install")

        for element in elements:
            hasFile: bool = "file" in element
            hasDirectory: bool = "directory" in element
            if hasFile == hasDirectory:
                raise ValueError(
                    "invalid element type found; each element must contain exactly one of 'file' or 'directory'"
                )

            if hasFile:
                fileElementRaw: Any = element["file"]
                if not isinstance(fileElementRaw, dict):
                    raise ValueError("file element must be an object")

                requiredFileKeys: tuple[str, ...] = (
                    "fileName",
                    "sourceDirectory",
                    "destination",
                    "type",
                )
                for key in requiredFileKeys:
                    if key not in fileElementRaw:
                        raise ValueError(f"file element is missing required key '{key}'")

                fileName: Any = fileElementRaw["fileName"]
                sourceDirectory: Any = fileElementRaw["sourceDirectory"]
                destination: Any = fileElementRaw["destination"]
                fileType: Any = fileElementRaw["type"]

                if not isinstance(fileName, str) or fileName == "":
                    raise ValueError("file element 'fileName' must be a non-empty string")
                if not isinstance(sourceDirectory, str):
                    raise ValueError("file element 'sourceDirectory' must be a string")
                if not isinstance(destination, str):
                    raise ValueError("file element 'destination' must be a string")
                if fileType not in ("copy", "link"):
                    raise ValueError("file element 'type' must be either 'copy' or 'link'")

            if hasDirectory:
                directoryElementRaw: Any = element["directory"]
                if not isinstance(directoryElementRaw, dict):
                    raise ValueError("directory element must be an object")

                requiredDirectoryKeys: tuple[str, ...] = (
                    "sourceName",
                    "destinationName",
                    "type",
                )
                for key in requiredDirectoryKeys:
                    if key not in directoryElementRaw:
                        raise ValueError(
                            f"directory element is missing required key '{key}'"
                        )

                sourceName: Any = directoryElementRaw["sourceName"]
                destinationName: Any = directoryElementRaw["destinationName"]
                directoryType: Any = directoryElementRaw["type"]

                if not isinstance(sourceName, str) or sourceName == "":
                    raise ValueError(
                        "directory element 'sourceName' must be a non-empty string"
                    )
                if not isinstance(destinationName, str):
                    raise ValueError(
                        "directory element 'destinationName' must be a string"
                    )
                if directoryType not in ("copy", "link"):
                    raise ValueError(
                        "directory element 'type' must be either 'copy' or 'link'"
                    )

    def install(self) -> bool:
        """
        Perform installation of files and directories.

        Returns:
            True if installation successful
        """
        if not self.loadConfig():
            return False

        try:
            self.validateConfig(cast(InstallConfig, self.config))
        except ValueError as e:
            print(f"Error: {e}")
            return False

        if not self.resolveProjectDirectory():
            return False

        manifestFileName: str = self.config["manifestFile"]
        if manifestFileName:
            manifestPath: Path = self.projectDir.joinpath(manifestFileName)
        else:
            manifestPath = None

        self.tracker = InstallationTracker(manifestPath) if manifestPath else None

        installDir: str = self.config["installDirectory"]
        if installDir:
            targetBaseDir: Path = self.projectDir.joinpath(installDir)
        else:
            targetBaseDir = self.projectDir

        try:
            targetBaseDir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"Error creating destination directory '{targetBaseDir}': {e}")
            return False

        elements: list[dict[str, Any]] = cast(list[dict[str, Any]], self.config["elements"])
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
            try:
                self.tracker.saveManifest()
            except (OSError, IOError, TypeError, ValueError) as e:
                print(f"Error writing manifest file '{manifestPath}': {e}")
                return False

        print("Installation completed successfully!")
        return True

    def _manifestRelativeFromScriptDir(self, pathValue: Path) -> str:
        """
        Convert a path to a script-directory-relative manifest path.

        Args:
            pathValue: Absolute path to convert

        Returns:
            Relative path string from script directory

        Raises:
            ValueError: If path cannot be represented relative to script directory
        """
        try:
            relativePath: Path = pathValue.relative_to(self.scriptDir)
        except ValueError as e:
            raise ValueError(
                f"Path cannot be represented relative to script directory: {pathValue}"
            ) from e

        return str(relativePath)

    def _manifestDestinationParts(
        self, destinationPath: Path
    ) -> tuple[str, Literal["scriptDir", "projectDir"]]:
        """
        Build manifest destination path and base hint for uninstall resolution.

        Args:
            destinationPath: Absolute destination path

        Returns:
            Tuple of relative destination path and destination base name

        Raises:
            ValueError: If destination cannot be represented relative to known bases
        """
        try:
            relativeToScript: Path = destinationPath.relative_to(self.scriptDir)
            return str(relativeToScript), "scriptDir"
        except ValueError:
            pass

        if self.projectDir is not None:
            try:
                relativeToProject: Path = destinationPath.relative_to(self.projectDir)
                return str(relativeToProject), "projectDir"
            except ValueError:
                pass

        raise ValueError(
            f"Destination cannot be represented relative to scriptDir or projectDir: {destinationPath}"
        )

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
                manifestSource: str = self._manifestRelativeFromScriptDir(sourceFile)
                manifestDestination, manifestBase = self._manifestDestinationParts(destFile)
                self.tracker.addFile(manifestSource, manifestDestination, manifestBase)

        except (OSError, IOError, ValueError) as e:
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
                manifestSource = self._manifestRelativeFromScriptDir(sourceDir)
                manifestDestination, manifestBase = self._manifestDestinationParts(destDir)
                self.tracker.addDirectory(
                    manifestSource,
                    manifestDestination,
                    manifestBase,
                )

        except (OSError, IOError, shutil.Error, ValueError) as e:
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

        try:
            self.validateConfig(cast(InstallConfig, self.config))
        except ValueError as e:
            print(f"Error: {e}")
            return False

        if not self.resolveProjectDirectory():
            return False

        manifestFileName: str = self.config["manifestFile"]
        if not manifestFileName:
            print("Error: No manifestFile defined in config")
            return False

        manifestPath: Path = self.projectDir.joinpath(manifestFileName)
        self.tracker = InstallationTracker(manifestPath)

        try:
            manifestLoaded: bool = self.tracker.loadManifest()
        except ValueError as e:
            print(f"Error: {e}")
            return False

        if not manifestLoaded:
            print(f"Error: Manifest file not found at {manifestPath}")
            return False

        installedItems: list[dict[str, Any]] = self.tracker.installedItems
        for i in range(len(installedItems) - 1, -1, -1):
            item: dict[str, Any] = installedItems[i]
            itemType: str = str(item.get("type", ""))

            destinationValue: Any = item.get("destination", "")
            if not isinstance(destinationValue, str) or destinationValue == "":
                print("Error: invalid manifest entry destination path")
                return False

            manifestDestinationPath: Path = Path(destinationValue)
            if manifestDestinationPath.is_absolute():
                print(
                    "Error: invalid manifest entry destination path; absolute paths are not allowed"
                )
                return False
            if ".." in manifestDestinationPath.parts:
                print(
                    "Error: invalid manifest entry destination path; traversal is not allowed"
                )
                return False

            destinationBaseValue: Any = item.get("destinationBase", "scriptDir")
            if destinationBaseValue == "projectDir":
                destPath: Path = self.projectDir.joinpath(manifestDestinationPath)
            elif destinationBaseValue == "scriptDir" or destinationBaseValue == "":
                destPath = self.scriptDir.joinpath(manifestDestinationPath)
            else:
                print("Error: invalid manifest entry destination base")
                return False

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
                print(f"Error removing {destinationValue}: {e}")
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
