# Python virtual environments, pip, requirements.txt, and dependency management

## Introduction

Python projects frequently depend on third-party packages. These packages can have their own versions, dependencies, operating-system requirements, and compatibility constraints. Managing those dependencies directly in a global Python installation can cause conflicts between unrelated projects.

A Python virtual environment provides an isolated environment for a project. It allows one project to use one set of packages while another project uses a different set.

This study script provides a practical progression from basic concepts to advanced dependency-management practices. It uses the standard-library `venv` module to create real temporary environments and uses `pip` through the selected Python interpreter to demonstrate package installation, inspection, dependency checking, and environment recreation.

The main concepts covered are:

- Python interpreters and environments
- virtual environments
- `venv`
- activation and deactivation
- `pip`
- `python -m pip`
- package installation and removal
- `requirements.txt`
- version specifiers
- dependency graphs
- direct and transitive dependencies
- `pip freeze`
- `pip check`
- editable installations
- wheels and source distributions
- Python package indexes
- hashes and artifact integrity
- environment variables
- import paths
- `pyproject.toml`
- constraints
- dependency categories
- environment markers
- extras
- reproducibility
- dependency locking
- security and supply-chain risks
- CI/CD dependency workflows
- performance
- troubleshooting
- production considerations

## Python installations and environments

A Python installation contains the Python interpreter and standard library. The interpreter executes Python programs, while the standard library provides modules such as `pathlib`, `json`, `hashlib`, and `subprocess`.

Third-party packages are distributed separately from Python itself. They are commonly installed using `pip`.

A simplified model is:

Python installation → interpreter → package installation location

A project-specific virtual environment introduces another layer:

Project → virtual environment → project-specific Python package environment

The virtual environment does not mean that the entire operating system is duplicated. It primarily provides isolation for Python packages and environment-specific configuration.

## Why package isolation matters

Suppose one project requires:

    example-package==1.5

while another project requires:

    example-package==2.4

A single global package directory cannot reliably represent both requirements at the same time.

Virtual environments solve this by providing independent package locations:

    analytics-project/
        .venv/
            example-package 1.5

    legacy-project/
        .venv/
            example-package 2.4

The two projects can therefore maintain different dependency versions without replacing each other's packages.

This isolation is one of the primary reasons virtual environments are standard practice for Python application development.

## The venv module

`venv` is part of Python's standard library. It provides a built-in mechanism for creating lightweight virtual environments.

The basic command is:

    python -m venv .venv

Here:

- `python` selects the interpreter.
- `-m venv` asks that interpreter to run the `venv` module.
- `.venv` is the directory where the environment is created.

The directory name `.venv` is conventional rather than mandatory.

A project could technically use another name, but `.venv` is widely recognizable and easy to exclude from version control.

The script also demonstrates `venv.EnvBuilder`, which allows an environment to be created programmatically.

## Typical virtual-environment structure

On Unix-like systems, a virtual environment commonly contains a structure resembling:

    project/
    ├── .venv/
    │   ├── bin/
    │   │   ├── python
    │   │   ├── pip
    │   │   └── activate
    │   ├── lib/
    │   │   └── pythonX.Y/
    │   │       └── site-packages/
    │   └── pyvenv.cfg
    ├── src/
    ├── tests/
    ├── requirements.txt
    └── README.md

Windows commonly uses:

    project/
    ├── .venv/
    │   ├── Include/
    │   ├── Lib/
    │   │   └── site-packages/
    │   ├── Scripts/
    │   │   ├── python.exe
    │   │   ├── pip.exe
    │   │   └── Activate.ps1
    │   └── pyvenv.cfg
    ├── src/
    ├── tests/
    ├── requirements.txt
    └── README.md

The exact contents can vary between Python versions and operating systems.

The environment directory is generated state. It is normally recreated rather than committed to source control.

## Activation

Activation changes the shell environment so that commands such as `python` and `pip` resolve to the virtual environment.

Windows PowerShell commonly uses:

    .venv\Scripts\Activate.ps1

Windows Command Prompt commonly uses:

    .venv\Scripts\activate.bat

Linux and macOS commonly use:

    source .venv/bin/activate

The active environment can then be left with:

    deactivate

Activation is convenient but not technically required.

An environment can be used directly by invoking its Python executable.

For example, Unix-like systems can use:

    .venv/bin/python -m pip --version

Windows can use:

    .venv\Scripts\python.exe -m pip --version

This distinction is important in automation because CI systems and deployment scripts should not depend unnecessarily on interactive shell activation.

## Detecting a virtual environment

The script examines:

    sys.executable
    sys.prefix
    sys.base_prefix

For a standard `venv` environment, `sys.prefix` and `sys.base_prefix` normally differ.

The Python executable is particularly important when diagnosing package problems.

A useful command is:

    python -c "import sys; print(sys.executable)"

If the displayed executable is not located in the intended `.venv` directory, commands may be running against the wrong Python installation.

## pip

`pip` is the standard package installer commonly used with Python environments.

Typical operations include:

    python -m pip --version

    python -m pip install requests

    python -m pip install requests==2.32.3

    python -m pip install --upgrade requests

    python -m pip uninstall requests

    python -m pip list

    python -m pip show requests

    python -m pip freeze

    python -m pip check

The script demonstrates these concepts without relying on modifications to the user's global environment.

## Why `python -m pip` is preferable

A computer may contain multiple Python installations:

    Python A
    Python B
    Project A .venv
    Project B .venv

A standalone `pip` command may resolve to a pip executable associated with a different interpreter.

Using:

    python -m pip

connects pip explicitly to the Python interpreter represented by `python`.

For example:

    python -m pip --version

can reveal which pip installation is being used.

This makes the command particularly useful when several Python installations exist on the same machine.

## Installing packages

A package can be installed with:

    python -m pip install package_name

An exact version can be requested with:

    python -m pip install package_name==1.2.3

An upgrade can be requested with:

    python -m pip install --upgrade package_name

The script creates temporary environments so package installation demonstrations do not alter the user's ordinary global Python environment.

Package installation may fail because of:

- no network access
- incompatible Python versions
- incompatible operating systems
- missing native build tools
- package-index configuration
- dependency conflicts
- unavailable package versions
- authentication failures for private repositories

Automation should always check the command's exit status.

## pip list

`pip list` shows packages currently installed in an environment.

A useful command is:

    python -m pip list

This provides an inventory of installed distributions.

It is particularly useful when investigating questions such as:

- Is a package installed?
- Which version is installed?
- Is an unexpected package present?
- Does the environment contain development dependencies?

The result describes the current environment, not necessarily the intended environment.

## pip show

`pip show` provides metadata about an installed package.

For example:

    python -m pip show requests

It can provide information such as:

- package name
- version
- installation location
- metadata
- declared requirements

The installation location is useful when diagnosing whether a package was installed into the expected virtual environment.

## pip freeze

`pip freeze` outputs installed package versions in an installation-oriented format.

A common workflow is:

    python -m pip freeze > requirements.txt

The resulting file can then be used with:

    python -m pip install -r requirements.txt

`pip freeze` is useful for recording the state of an environment. It is important to understand that a frozen environment is not automatically the same as a carefully designed direct-dependency specification.

For example, an application may directly depend on:

    requests

while `requests` itself depends on other packages.

A freeze operation can record the complete installed environment, including transitive dependencies.

## requirements.txt

A `requirements.txt` file is a plain-text dependency specification.

A simple file might contain:

    requests>=2.31,<3
    packaging>=24,<27
    pytest>=8,<9

Each line can describe a package and its version constraints.

The environment can be populated with:

    python -m pip install -r requirements.txt

Comments begin with `#` in normal requirements-file syntax.

The script includes a small educational parser to demonstrate the relationship between package names, operators, and versions. It intentionally does not attempt to implement the complete Python packaging grammar.

Production tooling should use pip and standards-compliant packaging mechanisms rather than a custom parser.

## Version specifiers

Common version operators include:

- `==` exact version
- `!=` excluded version
- `>=` minimum version
- `<=` maximum version
- `>` greater than
- `<` less than
- `~=` compatible release constraint

Examples:

    requests==2.32.3

requires exactly version `2.32.3`.

A range such as:

    requests>=2.31,<3

allows versions satisfying both conditions.

Version constraints are important because dependency compatibility is a constraint-solving problem.

Suppose one dependency requires:

    shared-library>=1,<3

and another requires:

    shared-library>=2,<4

The overlapping range is:

    shared-library>=2,<3

If another dependency requires:

    shared-library<2

there may be no single version satisfying all requirements.

A modern package installer attempts to resolve these constraints and can report an error when they cannot be satisfied.

## Direct and transitive dependencies

A direct dependency is a package that the application explicitly requires.

A transitive dependency is required by another dependency.

For example:

    application
        └── framework
            ├── router
            └── http-client
                └── url-parser

The application's direct dependency is `framework`.

`router`, `http-client`, and `url-parser` are transitive dependencies.

This distinction matters when maintaining dependency declarations. An application should generally declare the packages it directly depends on rather than manually treating every transitive dependency as a direct requirement.

## Dependency graphs

Dependencies form a graph rather than a simple list.

A project may depend on a framework. The framework may depend on an HTTP library. That HTTP library may depend on a URL parser.

This creates:

    Project
        ↓
    Framework
        ↓
    HTTP library
        ↓
    URL parser

As the dependency graph grows, the likelihood of compatibility interactions increases.

Dependency management therefore requires more than simply installing packages. It requires controlling versions, testing combinations, and understanding how dependencies interact.

## pip check

`pip check` examines installed distributions for dependency inconsistencies.

The command is:

    python -m pip check

A successful check indicates that pip's installed distribution metadata does not contain the relevant dependency conflicts.

This does not prove that the application itself works.

For example, an application can have perfectly consistent dependency metadata and still fail because of:

- application bugs
- invalid configuration
- unavailable external services
- incorrect credentials
- runtime logic errors
- unsupported operating-system behavior

`pip check` is therefore a useful validation step, not a complete application test.

## Importability versus distribution metadata

The script demonstrates two different concepts.

Python imports concern modules:

    import package_name

Package distributions concern installed project metadata.

A package can have a distribution name that differs from its Python import name.

For example, a distribution name may contain a hyphen while the corresponding import name uses an underscore.

Therefore:

    pip package name == import name

is not a safe assumption.

The `importlib.metadata` module provides access to installed distribution metadata without requiring the corresponding package to be imported.

## Package-name normalization

Python package distribution names have normalization rules.

Names containing combinations of hyphens, underscores, and periods can normalize to a common representation.

For example, conceptually:

    Example_Package
    example-package
    example.package

can correspond to the normalized name:

    example-package

This matters when interpreting package metadata and comparing distribution names.

## Editable installations

Editable installation is commonly used during package development.

The command is:

    python -m pip install -e .

The `-e` option requests editable installation.

The purpose is to allow the development environment to reference the source tree rather than requiring a conventional reinstall every time source files change.

Editable installation is useful for:

- package development
- local testing
- rapid iteration
- working on libraries while simultaneously consuming them

It should not automatically be assumed to be the same as a production installation.

Production deployments should use a deliberate packaging and artifact strategy.

## Wheels

A wheel is a built Python distribution format.

Wheels can significantly simplify installation because the package does not necessarily need to be built from source on the target machine.

A wheel can be:

- pure Python
- Python-version-specific
- operating-system-specific
- architecture-specific
- compiled

Pure-Python wheels are generally more portable.

Packages containing native extensions can depend on:

- compiler toolchains
- operating-system libraries
- CPU architecture
- Python ABI compatibility
- platform-specific build requirements

This is one reason why a dependency set that works on one machine may require different artifacts on another.

## Source distributions

A source distribution contains source and packaging information from which a package can be built.

Installing a source distribution can require build tools and build dependencies.

This can make installation slower or more complicated than installing a compatible prebuilt wheel.

Modern Python packaging uses build-system metadata to describe how distributions should be built.

## pyproject.toml

`pyproject.toml` is a standardized configuration file used by modern Python packaging.

It can contain:

- project metadata
- Python version requirements
- runtime dependencies
- optional dependencies
- build-system requirements
- build backend configuration
- configuration for other Python tools

A conceptual project definition might specify:

    [project]
    name = "example-project"
    version = "1.0.0"
    dependencies = [
        "requests>=2.31"
    ]

The build system can be described separately.

`requirements.txt` and `pyproject.toml` are not identical concepts.

A project can use `pyproject.toml` to describe package metadata and dependencies while using requirements files for environment-specific installation workflows.

## Dependency categories

Dependencies can be organized by purpose.

### Runtime dependencies

These are required for the application to operate.

Examples include:

- web frameworks
- database drivers
- HTTP libraries
- serialization libraries

### Development dependencies

These support development but may not be required by the deployed application.

Examples include:

- formatters
- linters
- development utilities

### Testing dependencies

These support automated tests.

A test framework such as pytest is usually not needed for the application to serve users in production.

### Build dependencies

These are needed to create a distributable package.

### Optional dependencies

These support features that only some users need.

Separating dependency categories helps reduce production environments and makes the project's dependency structure easier to understand.

## Environment markers

Environment markers allow dependency requirements to apply conditionally.

Examples include:

    colorama; platform_system == "Windows"

and:

    typing-extensions; python_version < "3.12"

This is useful when a dependency is needed only on certain operating systems or Python versions.

Markers can consider information such as:

- Python version
- operating system
- platform
- Python implementation
- processor architecture

Conditional requirements should be tested on every supported environment.

## Optional extras

Python packages can define optional dependency groups called extras.

Conceptually:

    package[database]

or:

    package[database,security]

An extra allows package authors to provide optional functionality without forcing every user to install every possible dependency.

This is useful for libraries supporting several database engines, integrations, or feature sets.

## Python-version compatibility

Dependency management is not limited to package versions.

The Python interpreter itself has compatibility requirements.

A project might support:

    Python >=3.11,<3.14

A dependency can have its own supported Python versions.

The final environment therefore has to satisfy several constraints:

- Python version
- package versions
- operating system
- architecture
- native libraries
- dependency relationships

A project should document and test its supported Python versions.

## Dependency constraints

A constraints file can restrict versions without serving as the project's direct dependency declaration.

For example, an application might declare:

    web-framework
    database-driver

while a constraints file specifies:

    shared-library==2.7.1

Installation can conceptually use:

    python -m pip install -r requirements.txt -c constraints.txt

The distinction is:

Requirements describe what should be installed.

Constraints describe which versions are permitted during resolution.

Constraints are useful when several projects or dependency declarations need to follow a consistent version policy.

## Dependency locking

Dependency locking records a resolved dependency set so that installations can reproduce a known state.

Three concepts should be distinguished:

### Dependency declaration

What the project directly requires.

### Dependency resolution

Which versions satisfy the complete set of constraints.

### Lock state

The concrete resolved environment intended to be reproduced.

For application deployments, locking can improve reproducibility because a fresh installation does not have to independently resolve potentially changing dependency versions.

The exact locking mechanism depends on the project's packaging and dependency-management tooling.

## Reproducibility

Reproducibility exists at different levels.

A weak environment may simply install packages without meaningful version constraints.

A stronger environment declares direct dependencies with tested version ranges.

A more controlled environment records a complete resolved dependency set.

An even stronger system can control exact artifacts using hashes and controlled package repositories.

Full deployment reproducibility may also require controlling:

- Python version
- operating system
- architecture
- system libraries
- environment variables
- external services
- deployment configuration

A requirements file alone cannot reproduce every part of a production system.

## Environment recreation

Virtual environments are intentionally disposable.

A clean workflow is:

    python -m venv .venv

Then install dependencies:

    python -m pip install -r requirements.txt

Then validate:

    python -m pip check

Then execute tests.

If an environment becomes corrupted or inconsistent, rebuilding it can be safer than manually manipulating its `site-packages` directory.

The script demonstrates deletion and recreation of temporary environments to illustrate this principle.

## Why .venv is normally excluded from Git

A virtual environment contains generated files and installed packages.

It is generally:

- machine-specific
- dependent on the Python installation
- large compared with source files
- reproducible from dependency declarations

A typical `.gitignore` includes:

    .venv/
    venv/
    __pycache__/
    *.py[cod]

The project should normally commit dependency declarations rather than the environment itself.

## Multiple Python installations

Multiple Python installations are common on development machines.

Examples include:

- operating-system Python
- a separately installed Python version
- a Python distribution
- multiple interpreter versions for different projects

This can create confusion when `python`, `python3`, and `pip` point to different installations.

Useful diagnostics include:

    python --version

    python -c "import sys; print(sys.executable)"

    python -m pip --version

On Windows, the `py` launcher and `where` command can help identify installed interpreters and executable resolution.

On Unix-like systems, `which` can show executable resolution.

## Windows PowerShell activation problems

PowerShell may restrict execution of scripts according to its execution policy.

As a result, an activation command such as:

    .venv\Scripts\Activate.ps1

can fail even when the virtual environment itself is correctly created.

One alternative is to bypass shell activation and invoke the environment directly:

    .venv\Scripts\python.exe -m pip --version

This is often useful for diagnostics and automation.

Security policy should not be weakened casually merely to make activation convenient.

## Unix-like activation and permissions

Linux and macOS commonly use:

    source .venv/bin/activate

The environment's Python executable can also be called directly:

    .venv/bin/python --version

and:

    .venv/bin/python -m pip --version

Direct execution is useful when debugging shell PATH issues.

## System-managed Python

Some operating systems rely on Python for system utilities or manage Python packages through an operating-system package manager.

Installing arbitrary packages into that environment can interfere with system-managed files.

Application dependencies should normally be installed into a project-specific virtual environment.

Administrative privileges should not be treated as a universal solution to pip installation problems.

## Externally managed environments

Modern Python packaging standards support the concept of externally managed Python environments.

An operating-system Python installation can indicate that it should not be modified directly by pip.

pip may then reject a global installation with an externally-managed-environment error.

This is intentional protection.

For application development, the normal response is to create a virtual environment rather than bypassing the protection without understanding its purpose.

## Environment variables

Virtual environments and pip can interact with environment variables.

Important examples include:

- `VIRTUAL_ENV`
- `PATH`
- `PYTHONPATH`
- `PIP_INDEX_URL`
- `PIP_EXTRA_INDEX_URL`

`PATH` controls executable discovery.

`PYTHONPATH` modifies Python's module search path and can introduce unexpected imports.

`VIRTUAL_ENV` is commonly present after activation.

pip also supports configuration through environment variables and configuration files.

Credentials should never be committed into source code or dependency files.

## Python import search path

Python uses `sys.path` to determine where it searches for importable modules.

The script displays the current path to demonstrate that environment configuration affects import resolution.

Import failures can result from:

- wrong Python interpreter
- wrong virtual environment
- local module shadowing
- unexpected `PYTHONPATH`
- stale editable installations
- multiple Python installations

Not every import problem is a pip problem.

## Local module shadowing

A project file named `json.py`, `requests.py`, `pandas.py`, or another common module name can accidentally shadow the intended package.

For example, if a project contains:

    json.py

an import of `json` may resolve to the local file rather than the standard-library module.

A useful diagnostic is:

    import package_name
    print(package_name.__file__)

This shows where Python actually loaded the module from.

## Dependency security

Package management is a software supply-chain concern.

Installing a package gives code from that package substantial execution privileges inside the environment.

Important risks include:

### Malicious packages

A package may contain intentionally harmful code.

### Typosquatting

A malicious package may use a name similar to a legitimate package.

### Dependency confusion

An internal package name can accidentally resolve to an untrusted public package.

### Compromised dependencies

A legitimate package or maintainer account can become compromised.

### Vulnerable dependencies

A package may contain a known security vulnerability.

### Installation-time execution

Package building and installation can execute code or build processes.

Security practices should therefore include:

- use trusted package sources
- control private package indexes
- review dependencies
- minimize unnecessary dependencies
- monitor vulnerabilities
- test upgrades
- protect repository credentials
- verify artifacts when required
- use controlled dependency updates
- avoid blindly trusting arbitrary package indexes

## Package indexes

PyPI is the primary public package repository used by the Python ecosystem.

Organizations may also operate private package indexes.

pip supports configuration such as:

- primary package index
- additional package index
- package credentials
- trusted hosts

These settings are security-sensitive.

Adding an arbitrary package index can introduce dependency-confusion and supply-chain risks.

Package sources should therefore be deliberately controlled.

## Hashes and artifact integrity

A package version identifies a release, but an exact artifact can be identified by its cryptographic hash.

SHA-256 is a common cryptographic hash algorithm.

A hash represents the bytes of an artifact.

Hash-based verification can provide stronger artifact-level reproducibility than version numbers alone.

This becomes important when an organization needs strict control over which downloaded files are accepted.

Hashes must be generated from trusted artifacts.

## Offline installation

Packages can be downloaded before installation.

A conceptual workflow is:

    python -m pip download -r requirements.txt -d packages/

An installation can then use the local directory:

    python -m pip install --no-index --find-links=packages/ -r requirements.txt

This can be useful for:

- restricted networks
- controlled build systems
- offline environments
- reproducible deployment pipelines

Offline installation does not automatically guarantee security. The artifacts must still originate from a trusted process.

## pip cache

pip can maintain a local cache of downloaded and built artifacts.

Useful commands include:

    python -m pip cache info

    python -m pip cache list

    python -m pip cache purge

Caching can improve installation speed.

In CI systems, caches should be keyed appropriately around factors such as:

- Python version
- operating system
- architecture
- dependency state
- package-manager configuration

Poor cache design can result in stale or incompatible artifacts being reused.

## Dependency bloat

Every additional dependency increases the potential maintenance surface.

Additional packages can introduce:

- security vulnerabilities
- compatibility requirements
- transitive dependencies
- larger installation sizes
- licensing considerations
- update requirements
- longer installation times

A project should avoid dependencies that do not provide meaningful value.

The standard library can be appropriate for simple functionality when it provides a sufficient solution.

## Performance considerations

Virtual environments themselves are lightweight compared with virtual machines.

Dependency installation performance depends on:

- network speed
- package size
- package cache
- wheel availability
- dependency graph size
- native compilation
- package-index performance

Wheels generally improve installation performance because prebuilt artifacts can avoid local compilation.

Native extensions may require compilers and system libraries, which can make installation substantially slower or more difficult.

## Build isolation

Modern Python packaging supports isolated build environments.

A project's build requirements can be described in `pyproject.toml`.

Build isolation prevents unrelated packages installed in a developer's environment from unintentionally determining how a project is built.

This is especially important for packages that require specific build tools or build-time dependencies.

## CI/CD dependency management

Continuous integration should create a clean environment rather than depending on packages accidentally installed on the CI runner.

A typical workflow is:

    source checkout
        ↓
    select supported Python
        ↓
    create isolated environment
        ↓
    install declared dependencies
        ↓
    validate dependencies
        ↓
    run tests
        ↓
    build artifacts
        ↓
    deploy validated artifacts

This process reduces the chance that an application succeeds only because a developer's machine contains undocumented packages.

## Virtual environments versus containers

A virtual environment and a container solve different isolation problems.

| Aspect | Virtual environment | Container |
|---|---|---|
| Main purpose | Python package isolation | Broader process and environment isolation |
| Isolation level | Python environment | Filesystem/process/network environment |
| Startup cost | Very low | Higher |
| Python included | Uses an installed interpreter | Often packages runtime inside the image |
| Typical use | Development, tests, Python applications | Deployment, services, CI |

They can also be used together.

A container can provide system-level isolation while Python packages are managed inside the container.

The appropriate architecture depends on the deployment requirements.

## Global installation versus virtual environments

| Property | Global installation | Virtual environment |
|---|---|---|
| Package isolation | Low | High |
| Project independence | Low | High |
| Version-conflict risk | Higher | Lower |
| Reproducibility | Weaker | Better |
| Suitable for application projects | Usually not preferred | Usually preferred |
| Environment recreation | Less controlled | Straightforward |

Global installation can be appropriate for some user-level command-line tools, but application dependencies should normally remain isolated.

## Dependency upgrades

Dependency upgrades require balancing several goals:

- security
- bug fixes
- new functionality
- compatibility
- reproducibility
- maintenance effort

A conservative project might pin exact versions.

A range-based project might use constraints such as:

    package>=2,<3

An organization may periodically upgrade dependencies and run a full test suite.

A version constraint should not be treated as proof of compatibility. Tests remain necessary.

## Semantic versioning

Many packages use the convention:

    MAJOR.MINOR.PATCH

The intended meaning is commonly:

- major: potentially breaking changes
- minor: backward-compatible features
- patch: backward-compatible fixes

Semantic versioning is a convention rather than an absolute guarantee.

Projects can interpret compatibility differently, and bugs can result in unexpected breaking behavior.

Dependency constraints should therefore be combined with testing.

## Dependency auditing

Dependency auditing examines the software components present in an environment.

Useful questions include:

- What packages are installed?
- Which versions are installed?
- Which dependencies are direct?
- Which are transitive?
- Are known vulnerable versions present?
- Are unnecessary packages installed?
- Where did artifacts come from?
- What licenses apply?
- Which packages contain native code?

Basic pip commands provide inventory information:

    python -m pip list
    python -m pip show package_name
    python -m pip freeze
    python -m pip check

Security-focused environments may add specialized dependency scanning and software-composition analysis.

## Error handling in automation

A package installation command is not successful merely because a subprocess was started.

Automation should inspect the process exit code.

Python's `subprocess.run()` supports:

    check=True

which raises an exception when the command exits unsuccessfully.

Using:

    check=False

allows explicit inspection of the return code.

The script demonstrates a deliberately invalid package installation to show how failure can be captured without terminating the entire educational program.

## Disposable environments

A virtual environment should generally be treated as disposable generated state.

If a project environment has become inconsistent, a clean recreation can be more reliable than manually modifying installed packages.

The basic strategy is:

    delete .venv
    create .venv again
    install declared dependencies
    run validation
    run tests

This works particularly well when dependency declarations are maintained carefully.

## Common mistakes

### Installing every package globally

This causes projects to compete over package versions.

Use project-specific environments.

### Using the wrong pip

A standalone `pip` can belong to another Python installation.

Use:

    python -m pip

and inspect:

    sys.executable

### Committing .venv

The environment is generated and machine-specific.

Commit dependency declarations instead.

### Using uncontrolled versions

Unbounded dependencies can produce different environments over time.

Use tested version constraints or an appropriate locking strategy.

### Treating pip freeze as a complete dependency-design method

`pip freeze` reports the current installed state. It does not necessarily communicate which packages are direct application requirements.

### Ignoring Python versions

A package can be compatible with one Python version and incompatible with another.

Declare and test supported Python versions.

### Copying site-packages

Copying package directories between machines is unreliable, especially when packages contain compiled extensions.

Recreate environments instead.

### Assuming package names equal import names

Distribution names and import names can differ.

Inspect metadata or documentation.

### Disabling security controls without understanding them

Examples include bypassing externally managed environment protections or blindly trusting package hosts.

Understand the reason for the protection before changing it.

## Important edge cases

### Multiple Python installations

Always verify the exact interpreter.

### Removed Python interpreter

An existing virtual environment can become unusable if the Python installation it references is removed or changed significantly.

Recreating the environment is usually safer.

### Native extensions

Binary compatibility can depend on Python version, operating system, architecture, and system libraries.

### Operating-system differences

A dependency snapshot does not guarantee that identical wheel artifacts exist on every platform.

### Network restrictions

pip may be unable to access its package index.

Controlled offline installation may be required.

### Private packages

Private repositories require secure authentication and carefully controlled package-index configuration.

### Editable installations

Editable installations are useful for development but should not automatically be treated as production artifacts.

### Shell differences

Activation commands vary between PowerShell, Command Prompt, bash, zsh, and other shells.

## Production considerations

Production environments should be created from controlled dependency information rather than a developer's accidental local package state.

Important production concerns include:

- supported Python version
- controlled dependencies
- reproducible installation
- security scanning
- trusted package sources
- artifact integrity
- CI validation
- test coverage
- environment configuration
- secret management
- controlled upgrades
- rollback capability
- deployment isolation

A production environment should be deterministic enough that a clean deployment does not depend on undocumented packages from an engineer's workstation.

## Project structure

A practical Python project can use a structure such as:

    project/
    ├── .venv/
    ├── src/
    │   └── application/
    ├── tests/
    ├── requirements.txt
    ├── .gitignore
    ├── pyproject.toml
    └── README.md

The exact structure depends on the project's packaging and deployment model.

The important principle is to separate:

- source code
- tests
- dependency declarations
- generated environments
- generated caches
- documentation
- configuration

## Practical workflow

A straightforward project workflow is:

    python -m venv .venv

Activate the environment if desired.

Then verify the interpreter:

    python -c "import sys; print(sys.executable)"

Verify pip:

    python -m pip --version

Install dependencies:

    python -m pip install -r requirements.txt

Check dependency consistency:

    python -m pip check

Run tests:

    python -m pytest

The test command requires pytest to be installed in the selected environment.

For CI, the same sequence should be performed in a fresh environment rather than relying on previously installed runner packages.

## Design principles demonstrated by the script

The Python script intentionally uses temporary environments for demonstrations involving real package installation.

This provides several useful properties:

- global packages are not intentionally modified
- environments can be deleted after testing
- examples are reproducible
- package isolation can be observed directly
- pip can be invoked through an explicit interpreter
- failures can be handled programmatically

The script also contains educational implementations of version comparison, package-name normalization, requirement parsing, dependency graphs, and environment validation.

These implementations are demonstrations rather than replacements for pip or Python's packaging standards.

## Relationship between the major components

The main components fit together as follows:

    Python interpreter
            |
            v
    venv creates isolated environment
            |
            v
    environment-specific Python
            |
            v
    python -m pip
            |
            +---- install packages
            |
            +---- remove packages
            |
            +---- inspect packages
            |
            +---- check dependencies
            |
            +---- freeze installed state
            |
            v
    requirements.txt / project metadata
            |
            v
    reproducible environment creation

For more advanced packaging, `pyproject.toml`, constraints, lock information, artifact hashes, private indexes, and CI/CD controls can be layered onto this foundation.

## Limitations of requirements.txt

`requirements.txt` is useful and widely supported, but it is not a universal representation of every aspect of an environment.

It may not fully describe:

- Python interpreter installation
- operating-system libraries
- external services
- environment variables
- system-level tools
- CPU architecture
- deployment infrastructure

A complete production environment therefore requires controls beyond a single dependency file.

## Implementation considerations

The script uses only Python's standard library for its educational infrastructure.

Important standard-library components include:

- `venv` for virtual-environment creation
- `subprocess` for executing pip and Python commands
- `pathlib` for cross-platform paths
- `sys` for interpreter information
- `platform` for platform information
- `importlib.util` for import discovery
- `importlib.metadata` for installed distribution metadata
- `hashlib` for cryptographic hashes
- `tempfile` for temporary environments
- `shutil` for cleanup
- `dataclasses` for structured examples
- `re` for the deliberately simplified requirements parser

Some demonstrations install the lightweight `packaging` distribution into a temporary environment. If network access is unavailable, the installation demonstration reports the failure rather than modifying the global environment or pretending the installation succeeded.

## Testing considerations

The script contains internal assertions covering:

- package-name normalization
- version parsing
- version comparisons
- basic requirement parsing

It also performs real environment-level operations, including:

- virtual-environment creation
- pip inspection
- dependency installation where network access permits
- dependency checking
- package metadata inspection
- environment recreation

The combination demonstrates an important distinction between unit-level logic tests and environment-level validation.

A dependency file can be syntactically valid while the resulting application still fails. Real testing must therefore include the application's behavior.

## Security considerations

Dependency management should be treated as part of application security.

A secure process considers:

- source authenticity
- package provenance
- package vulnerabilities
- version selection
- artifact integrity
- private repository configuration
- secret handling
- dependency minimization
- update testing

The most important operational principle is that a dependency is executable third-party software, not merely a line in a text file.

## Real-world relevance

Python virtual environments are relevant to:

- web applications
- data analysis
- machine learning
- automation
- scientific computing
- backend services
- command-line applications
- testing
- CI/CD
- package development
- internal enterprise applications
- production deployment

The core practice remains the same: keep project dependencies isolated, declare them explicitly, validate them in clean environments, and control the dependency supply chain according to the application's requirements.
