# infraInstall
Simple Installer that can be leveraged by other project to do setup.

|**file**|**description**|
|---|---|
|install.spec.md|The specification for the installer and Unit Test|
|install.py|The main installer/uninstaller|
|install_test.py|Unit test for the installer|

Example
|infraInstall|infraDevContainer|infraVerilog|
|---|---|---|
|||infraDevContainer.manifest.json|
|||./devcontainer|
|||file1|
|||file2|
|||/infraDevContainer|
||install.config.json|install.config.json|
||install.py|install.py|
||file1|file1|
||file2|file2|
||/ifraInstall|/infraDevcontainer/infraInstall
|install.config.json|install.config.json|install.config.json
|install.py|install.py|install.py
