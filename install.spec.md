# install.spec.md
This is a specification for the install.py script.

## The project
This repo is intended as a generic installer to help setup other repos. 
This repo will be installed as a git submodule to a parent repo.

The installer must read the install.config.json to decide how to install the files in the parent repo.

### install.config.json definition
```json
{
"projectDirectory":"",
"installDirectory":"",
"manifestFile":"",
"elements":[
    {"file":{
        "fileName":"",
        "sourceDirectory":"",
        "destination":"",
        "type":"copy"|"link"}
    },
    {"directory":{
        "sourceName":"",
        "destinationName":"",
        "type":"copy"|"link"
    }}
]
}
```

### Configuration File Loading and Validation
- The install.config.json file must exist in the script directory. If the file does not exist, the script must exit with non-zero status and print a clear error message indicating the file path that was not found.
- The install.config.json file must contain valid JSON. If the JSON is malformed, the script must exit with non-zero status and print a clear error message describing the JSON parse error.
- The config must contain all required top-level keys: projectDirectory, installDirectory, manifestFile, and elements. If any of these keys are missing, the script must exit with non-zero status and warn the user.
- The top-level value types must be correct: projectDirectory, installDirectory, and manifestFile must be strings; elements must be an array. If any value has an incorrect type, the script must exit with non-zero status and warn the user.

**projectDirectory**
- This key defines the directory to install the files.
- If this value is "" then copy to the to the parent repo.
- The resolved projectDirectory path must exist. If the path does not exist, the script must exit with non-zero status and warn the user.
- Path traversal references (e.g., ../) are not allowed. The projectDirectory value must reference a path that exists relative to the script directory.

**installDirectory**
- This key defines a direcory in the parent directory to copy the files too.
- If this value is "" then copy to the projectDirectory.

**manifestFile**
- This key defines the name of the manifest file to create.
- The manifestFile should be placed in projectDirectory
- If this value is blank then no manifestFile should be created.

**elements**
- This key defines the array of items to be installed.
- If the array is empty then the script should exit and the user should be warned.
- If multiple elements resolve to the same destination path, elements are applied in config order and the later element determines the final state at that path. Install should not fail solely because of this conflict.
- Unknown extra keys inside file or directory elements are ignored. Install should continue as long as required keys and values are valid.
- Each array item can either a "file" or a "directory". 
    - If the element is something other then file or directory, the script should exit the user should be warned.
- The following are the definitions.
    **file element**
    - A key of file specifies a file operation.
    - The fileName key is the name of the file
        - If this key is missing then exit and warn the user.
        - if the value is empty then exit and warn the user.
    - The sourceDirectory key indicates a subdirectory within this repo where the file can be found
        - If this key is missing then exit and warn the user.
        - if the value is empty then the file can be found in the top level of the repo.
    - The fileName key is the name of the file to locate. The source file must exist. If the source file does not exist at the resolved source path, the script must exit with non-zero status and warn the user.
    - The destinationDirectory key indicates a sub directory in parentDirectory that the file should be placed in.
        - If this key is missing then exit and warn the user.
        - if the value is empty then the file can be placed in the parent repo.
    - The type key indicates the type of connection from this repo to the parent repo. There are two options: copy or link.
        - A copy value means copy the file to the destinationDirectory.
        - A key value means create a linux symbolic link from file the destinationDirectory.
        - If the key is missing then exit and warn the user.
        - If the value is not copy or key then exit and warn the user.
    - If a file element type is link and a destination file or symlink already exists, it will be removed first, then the symlink will be created. If removal fails due to permissions, the install will fail with an error message.
    - If symlink creation fails (due to permissions or platform limitations), the install must exit with non-zero status and print an error message.
    - If a destination file already exists during a copy operation, it will be overwritten.

    **directory element**
    - The directory key means we are performing a directory operation.
        - If this key is missing then exit and warn the user.
        - if the value is empty then exit and warn the user.
    - The sourceName key is the name of the directory in this repo.
        - If this key is missing then exit and warn the user.
        - if the value is empty then exit and warn the user.
        - The source directory must exist at the resolved source path. If it does not exist, the script must exit with non-zero status and warn the user.
    - The destinationName is the name of the directory in the parent repo.
        - If this key is missing then exit and warn the user.
        - if the value is empty then use the sourceName for the destinationName.
    - The type key can either be copy or link.
        - A copy value means recursivily copy the directory to the parent repo.
        - A link value means recursicily create a linux symbolic link from the parent rep to the sourceName.
        - If the key is missing then exit and warn the user.
        - If the value is not copy or key then exit and warn the user.
    - If a directory element type is link and a destination directory or symlink already exists, it will be removed first, then the symlink will be created. If removal fails due to permissions, the install will fail with an error message.
    - If symlink creation fails (due to permissions or platform limitations), the install must exit with non-zero status and print an error message.
    - If a destination directory already exists during a copy operation, it will be deleted and replaced with the new directory.

### Command Line Options
- install.py should have two options install or uninstall
#### Install
- For the install option, install.py should install based the install.config.json file.
- If the manifest file name is specified in install.config.json, the install should create the manifest file in the projectDirectory (as specified in the manifestFile definition above).
- If an element installation fails, the install will stop processing remaining elements. Previously installed items are NOT rolled back. The installer will exit with non-zero status and report failure.
- If the destination parent path cannot be created (for example due to permissions), install.py must exit with non-zero status and print the OS error.
- If manifest writing fails, install.py must exit with non-zero status and report the write error. Previously installed items are NOT rolled back.
- If the manifest file already exists before install, it will be overwritten with a fresh manifest for the current run (not merged). Install should not fail solely because the file already exists.
- Running install multiple times with the same config should be idempotent: each run should succeed and converge to the same installed state and manifest content for that config.
#### Uninstall
- For the uninstall option, install.py should remove the files it created in the parent repo.
- If the manifest file is missing during uninstall, install.py must exit with non-zero status and report that the manifest was not found.
- If the manifest file is malformed during uninstall, install.py must exit with non-zero status and report the parse error.
- If destination paths listed in the manifest are already missing during uninstall, install.py should continue processing remaining entries and still succeed.
- If config is changed to point at a different manifest path than the one used during install and that manifest does not exist, uninstall must exit with non-zero status and report manifest not found. No installed items should be removed in that case.
- Uninstall is not idempotent: after a successful uninstall removes the manifest, a second uninstall with the same config should fail with non-zero status because the manifest is missing.

## Instructions for the python developer agent

- Name the file you create install.py.
- The file should be written in python.

- Name the config file install.config.json.
- The config file should be in json.
- The default configuration file the repo should be as follows:
```json
{
"projectDirectory":"",
"installDirectory":"",
"manifestFile":"",
"elements":[
    {"file":{
        "fileName":"install.py",
        "sourceDirectory":"",
        "destination":"",
        "type":"link"}
    },
    {"file":{
        "fileName":"install.config.json",
        "sourceDirectory":"",
        "destination":"",
        "type":"copy"}
    },
    {"directory":{
        "sourceName":"",
        "destinationName":"",
        "type":"copy"|"link"
    }}
]
}

```
