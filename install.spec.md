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

**projectDirectory**
- This key defines the directory to install the files.
- A value of "" means copy to the to the parent repo.

**installDirectory**
- This key defines a direcory in the parent directory to copy the files too.

**manifestFile**
- This key defines the name of the manifest file to create.
- A value of blank means no manifestFile should be created.

**elements**
- This key defines the array of items to be installed.
- Each array item can either a "file" or a "directory". The following are the definitions.
    **file element**
    - A key of file specifies a file operation.
    - The fileName key is the name of the file
    - The sourceDirectory key indicates a subdirectory within this repo where the file can be found
    - The destinationDirectory key indicates a sub directory in parentDirectory that the file should be placed in.
    - The type key indicates the type of connection from this repo to the parent repo. There are two options: copy or link.
        - A copy value means copy the file to the destinationDirectory.
        - A key value means create a linux symbolic link from file the destinationDirectory.

    **directory element**
    - The directory key means we are performing a directory operation.
    - The sourceName key is the name of the directory in this repo.
    - The destinationName is the name of the directory in the parent repo.
    - The type key can either be copy or link.
        - A copy value means recursivily copy the directory to the parent repo.
        - A link value means recursicily create a linux symbolic link from the parent rep to the sourceName.

### Command Line Options
- install.py should have two options install or uninstall
#### Install
- For the install option, install.py should install based the install.config.json file.
- If the manifest file name is specified in install.config.json, the install should create the manifest file in the home directory.
#### Uninstall
- For the uninstall option, install.py should remove the files it created in the parent repo.

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
