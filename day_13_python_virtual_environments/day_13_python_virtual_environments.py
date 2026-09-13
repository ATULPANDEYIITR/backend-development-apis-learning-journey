"""
Python Virtual Environments
===========================

A comprehensive executable study file covering:

- Python package management
- pip
- virtual environments
- venv
- dependency isolation
- requirements.txt
- dependency inspection
- package installation and removal
- version constraints
- reproducible environments
- dependency conflicts
- editable installations
- wheels and source distributions
- Python package indexes
- environment discovery and troubleshooting
- subprocess-based environment management
- security considerations
- production practices
- advanced dependency-management concepts

The demonstrations are designed to run without third-party dependencies.
Some examples intentionally use hypothetical package names or temporary
directories to explain package-management concepts safely.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import venv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


# =============================================================================
# 1. FUNDAMENTAL CONCEPTS
# =============================================================================

def section(title: str) -> None:
    """Print a clearly separated educational section."""
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def explain_python_installation() -> None:
    """
    Explain the relationship between Python, pip, site-packages, and venv.

    Python itself is the interpreter.
    pip is a package installer and dependency-management interface.
    venv creates an isolated Python environment.
    site-packages is where installed third-party packages normally live.
    """
    section("1. Python installation, pip, and virtual environments")

    print(
        textwrap.dedent(
            """
            Python has an interpreter and a standard library. Third-party
            packages are normally installed into a site-packages directory.

            pip is commonly used to install packages from a package index or
            another supported source.

            A virtual environment is an isolated directory containing the
            environment-specific Python executable and package installation
            location.

            A virtual environment does not duplicate the entire operating
            system or necessarily contain a completely independent copy of
            every system component. It primarily separates Python packages
            and environment configuration from other Python environments.

            Example conceptual relationship:

                Operating system
                    |
                    +-- Python installation
                    |      |
                    |      +-- standard library
                    |      +-- pip
                    |      +-- global packages
                    |
                    +-- Project A
                    |      |
                    |      +-- .venv
                    |             +-- Python
                    |             +-- site-packages
                    |
                    +-- Project B
                           |
                           +-- .venv
                                  +-- Python
                                  +-- site-packages
            """
        ).strip()
    )


# =============================================================================
# 2. PYTHON VERSION AND EXECUTABLE INFORMATION
# =============================================================================

def inspect_current_python() -> None:
    """Display information about the interpreter running this script."""
    section("2. Inspecting the active Python interpreter")

    print(f"Python version : {platform.python_version()}")
    print(f"Implementation : {platform.python_implementation()}")
    print(f"Executable     : {sys.executable}")
    print(f"Prefix         : {sys.prefix}")
    print(f"Base prefix    : {sys.base_prefix}")
    print(f"Platform       : {platform.platform()}")

    in_virtual_environment = sys.prefix != sys.base_prefix

    print(f"Virtual env    : {in_virtual_environment}")

    if in_virtual_environment:
        print("This Python process is running inside a virtual environment.")
    else:
        print(
            "This Python process is not running inside a standard venv-style "
            "virtual environment."
        )

    print(
        """
        Important distinction:

        sys.executable
            Points to the Python executable being used by this process.

        sys.prefix
            Points to the active Python environment prefix.

        sys.base_prefix
            Usually identifies the base Python installation from which a venv
            was created.

        For a standard venv, comparing sys.prefix and sys.base_prefix is a
        practical way to detect whether the interpreter is inside that venv.
        """
    )


# =============================================================================
# 3. IMPORTS AND PACKAGE DISCOVERY
# =============================================================================

def demonstrate_standard_library_vs_external_package() -> None:
    """
    Demonstrate that standard-library modules do not need pip.

    pathlib and hashlib are standard-library modules.
    """
    section("3. Standard-library modules versus third-party packages")

    print("pathlib is available:", importlib.util.find_spec("pathlib") is not None)
    print("hashlib is available:", importlib.util.find_spec("hashlib") is not None)

    print(
        """
        Standard-library modules are distributed with Python and normally do
        not need to be installed with pip.

        Third-party packages are distributed separately and are commonly
        installed into the active environment.

        Example third-party packages include:

            requests
            numpy
            pandas
            fastapi
            django
            pytest

        Installing a third-party package globally can create conflicts between
        unrelated projects. A virtual environment avoids most of these
        project-to-project package conflicts.
        """
    )


# =============================================================================
# 4. WHY VIRTUAL ENVIRONMENTS EXIST
# =============================================================================

@dataclass
class ProjectDependency:
    """Represent a dependency requirement for a hypothetical project."""

    project_name: str
    package_name: str
    required_version: str


def demonstrate_dependency_conflict() -> None:
    """Show why different projects may require incompatible package versions."""
    section("4. Dependency isolation and version conflicts")

    project_a = ProjectDependency(
        project_name="analytics-project",
        package_name="example-package",
        required_version="1.5",
    )

    project_b = ProjectDependency(
        project_name="legacy-project",
        package_name="example-package",
        required_version="2.4",
    )

    print(
        f"{project_a.project_name} requires "
        f"{project_a.package_name}=={project_a.required_version}"
    )
    print(
        f"{project_b.project_name} requires "
        f"{project_b.package_name}=={project_b.required_version}"
    )

    print(
        """
        If both projects share one global site-packages directory, installing
        one version can replace or conflict with the other.

        With separate virtual environments:

            analytics-project/
                .venv/
                    example-package 1.5

            legacy-project/
                .venv/
                    example-package 2.4

        Each project gets an independent package installation environment.
        """
    )


# =============================================================================
# 5. CREATING A VIRTUAL ENVIRONMENT PROGRAMMATICALLY
# =============================================================================

def create_temporary_virtual_environment() -> Path:
    """
    Create a real temporary virtual environment.

    The environment is created outside the current project and removed when
    this function's caller removes the temporary directory.
    """
    temporary_root = Path(tempfile.mkdtemp(prefix="python_venv_demo_"))
    environment_directory = temporary_root / ".venv"

    print(f"Creating virtual environment at: {environment_directory}")

    builder = venv.EnvBuilder(
        system_site_packages=False,
        clear=False,
        symlinks=False,
        with_pip=True,
        upgrade_deps=False,
    )

    builder.create(environment_directory)

    return temporary_root


def virtual_environment_python(environment_directory: Path) -> Path:
    """Return the Python executable path for a virtual environment."""
    if os.name == "nt":
        return environment_directory / "Scripts" / "python.exe"

    return environment_directory / "bin" / "python"


def virtual_environment_pip(environment_directory: Path) -> list[str]:
    """
    Return a reliable pip invocation.

    Using `python -m pip` is preferable to depending on a shell-resolved
    standalone `pip` command because it explicitly associates pip with the
    selected Python interpreter.
    """
    python_path = virtual_environment_python(environment_directory)
    return [str(python_path), "-m", "pip"]


def demonstrate_real_venv_creation() -> None:
    """Create, inspect, and remove an actual temporary virtual environment."""
    section("5. Creating and inspecting a real virtual environment")

    temporary_root = create_temporary_virtual_environment()

    try:
        environment_directory = temporary_root / ".venv"
        python_path = virtual_environment_python(environment_directory)

        print(f"Environment directory: {environment_directory}")
        print(f"Python executable     : {python_path}")
        print(f"Executable exists     : {python_path.exists()}")

        completed = subprocess.run(
            [str(python_path), "-c", "import sys; print(sys.executable); print(sys.prefix); print(sys.base_prefix)"],
            capture_output=True,
            text=True,
            check=True,
        )

        print("\nInterpreter information inside the new environment:")
        print(completed.stdout.strip())

        print("\nVirtual environment directory contents:")
        for path in sorted(environment_directory.iterdir()):
            print(f"  {path.name}")

        print(
            """
            The environment has its own interpreter entry point and its own
            package installation location.

            Activation is optional. Commands can also directly target the
            environment's Python executable.
            """
        )

    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)
        print(f"\nTemporary environment removed: {not temporary_root.exists()}")


# =============================================================================
# 6. ACTIVATION
# =============================================================================

def explain_activation() -> None:
    """Explain activation without depending on the current shell."""
    section("6. Activation and deactivation")

    print(
        """
        Activation modifies the current shell's environment so that commands
        such as `python` and `pip` resolve to the virtual environment.

        Typical commands:

        Windows PowerShell:
            .venv\\Scripts\\Activate.ps1

        Windows Command Prompt:
            .venv\\Scripts\\activate.bat

        Linux or macOS:
            source .venv/bin/activate

        Deactivation:
            deactivate

        Activation is a convenience, not a requirement.

        This:

            python -m pip install requests

        after activation normally targets the active venv.

        The explicit equivalent without activation is conceptually:

            .venv/bin/python -m pip install requests

        on Unix-like systems, or:

            .venv\\Scripts\\python.exe -m pip install requests

        on Windows.

        A common debugging technique is:

            python -c "import sys; print(sys.executable)"

        If the executable is not the expected .venv interpreter, the command
        is probably using the wrong environment.
        """
    )


# =============================================================================
# 7. PYTHON -M PIP
# =============================================================================

def explain_python_m_pip() -> None:
    """Explain why python -m pip is a robust command pattern."""
    section("7. Why `python -m pip` is preferred")

    print(
        """
        Consider a machine with:

            Python A
            Python B
            Project A .venv
            Project B .venv

        A standalone `pip` command may resolve to a pip executable associated
        with a different Python installation.

        `python -m pip` asks the selected Python interpreter to execute pip.

        Therefore:

            python -m pip --version

        can show which Python environment owns that pip installation.

        A useful diagnostic command is:

            python -m pip --version

        The output normally includes both the pip version and the location of
        the pip package.

        The same principle applies to other Python tools:

            python -m pytest
            python -m build
            python -m pip
        """
    )


# =============================================================================
# 8. PIP COMMANDS
# =============================================================================

def explain_pip_commands() -> None:
    """Explain the principal pip operations."""
    section("8. Core pip commands")

    commands = {
        "Check pip": "python -m pip --version",
        "Install package": "python -m pip install package_name",
        "Install exact version": "python -m pip install package_name==1.2.3",
        "Upgrade package": "python -m pip install --upgrade package_name",
        "Uninstall package": "python -m pip uninstall package_name",
        "List installed packages": "python -m pip list",
        "Show package metadata": "python -m pip show package_name",
        "Freeze environment": "python -m pip freeze",
        "Check dependency consistency": "python -m pip check",
        "Install requirements": "python -m pip install -r requirements.txt",
        "Download package artifacts": "python -m pip download package_name",
        "Inspect package index information": "python -m pip index versions package_name",
    }

    for description, command in commands.items():
        print(f"{description:<32} {command}")


# =============================================================================
# 9. REQUIREMENTS.TXT
# =============================================================================

def explain_requirements_file() -> None:
    """Explain requirements.txt syntax and reproducibility."""
    section("9. requirements.txt")

    print(
        """
        requirements.txt is a plain-text dependency specification.

        Example conceptual file:

            requests==2.32.3
            packaging>=24.0,<26
            pytest>=8,<9

        Version operators have different meanings:

            ==  exact version
            >=  minimum version
            <=  maximum version
            >   greater than
            <   less than
            ~=  compatible release constraint
            !=  excluded version

        Examples:

            requests==2.32.3

        means exactly version 2.32.3.

            requests>=2.31,<3

        allows versions in the supported range while excluding version 3 or
        later.

        A requirements file can also contain options, comments, local paths,
        URLs, and environment markers depending on the packaging scenario.

        Installing:

            python -m pip install -r requirements.txt

        Exporting the current environment:

            python -m pip freeze > requirements.txt

        Important distinction:

        `pip freeze` describes the packages currently installed in an
        environment. It is not automatically the same thing as a carefully
        designed direct-dependency specification.

        A mature project may distinguish direct dependencies from the complete
        resolved dependency set.
        """
    )


# =============================================================================
# 10. REQUIREMENTS FILE PARSING
# =============================================================================

REQUIREMENT_PATTERN = re.compile(
    r"^\s*([A-Za-z0-9_.-]+)\s*(==|!=|~=|>=|<=|>|<)?\s*([^\s;#]+)?"
)


def parse_requirement_line(line: str) -> tuple[str, str, str] | None:
    """
    Parse a simple package requirement.

    This intentionally does not implement the complete packaging grammar.
    The purpose is educational: demonstrate the basic name/operator/version
    structure without pretending to replace pip's standards-compliant parser.
    """
    stripped = line.strip()

    if not stripped or stripped.startswith("#"):
        return None

    match = REQUIREMENT_PATTERN.match(stripped)

    if not match:
        return None

    package_name = match.group(1)
    operator = match.group(2) or ""
    version = match.group(3) or ""

    return package_name, operator, version


def demonstrate_requirement_parser() -> None:
    """Demonstrate basic requirements-file syntax parsing."""
    section("10. Reading simple requirements.txt entries")

    examples = [
        "requests==2.32.3",
        "packaging>=24.0",
        "pytest>=8,<9",
        "example-package~=1.4",
        "# This is a comment",
        "",
    ]

    for line in examples:
        parsed = parse_requirement_line(line)

        if parsed is None:
            print(f"{line!r:30} -> ignored or unsupported by this simple parser")
        else:
            package_name, operator, version = parsed
            print(
                f"{line!r:30} -> "
                f"name={package_name!r}, operator={operator!r}, version={version!r}"
            )

    print(
        """
        The parser above intentionally handles only a small educational subset.
        Real package requirements can contain extras, environment markers,
        direct URLs, local paths, VCS references, hashes, and more.

        Application code should not be used as a replacement for pip or the
        packaging ecosystem's requirement parser.
        """
    )


# =============================================================================
# 11. VERSION SPECIFIERS
# =============================================================================

@dataclass(frozen=True)
class Version:
    """Minimal semantic version representation for educational comparisons."""

    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> "Version":
        numbers = value.split(".")
        if len(numbers) != 3:
            raise ValueError("Expected a three-part version such as 2.4.1")

        return cls(*(int(part) for part in numbers))

    def as_tuple(self) -> tuple[int, int, int]:
        return self.major, self.minor, self.patch

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def version_satisfies(
    version: Version,
    operator: str,
    target: Version,
) -> bool:
    """Evaluate a small subset of version constraints."""
    left = version.as_tuple()
    right = target.as_tuple()

    if operator == "==":
        return left == right
    if operator == "!=":
        return left != right
    if operator == ">":
        return left > right
    if operator == ">=":
        return left >= right
    if operator == "<":
        return left < right
    if operator == "<=":
        return left <= right

    raise ValueError(f"Unsupported operator: {operator}")


def demonstrate_version_comparison() -> None:
    """Show why version constraints matter."""
    section("11. Version constraints and dependency compatibility")

    installed = Version.parse("2.5.1")
    minimum = Version.parse("2.0.0")
    maximum = Version.parse("3.0.0")

    print(f"Installed version: {installed}")
    print(
        f">= {minimum}:",
        version_satisfies(installed, ">=", minimum),
    )
    print(
        f"< {maximum}:",
        version_satisfies(installed, "<", maximum),
    )

    print(
        """
        Dependency resolution is fundamentally a constraint problem.

        If package A requires:

            shared-library>=1,<3

        and package B requires:

            shared-library>=2,<4

        the overlapping valid range is:

            shared-library>=2,<3

        If one package requires:

            shared-library<2

        while another requires:

            shared-library>=3

        no single version can satisfy both constraints.

        pip may report a dependency resolution error rather than silently
        installing an incompatible combination.
        """
    )


# =============================================================================
# 12. DEPENDENCY GRAPH
# =============================================================================

@dataclass
class DependencyNode:
    """Represent a package and its direct dependencies."""

    name: str
    dependencies: list[str]


def dependency_graph_demo() -> None:
    """Build and display a small dependency graph."""
    section("12. Dependency graphs")

    graph = {
        "application": ["web-framework", "database-driver"],
        "web-framework": ["routing-library", "serialization-library"],
        "database-driver": ["serialization-library"],
        "routing-library": [],
        "serialization-library": [],
    }

    def visit(package: str, depth: int = 0) -> None:
        print("  " * depth + package)

        for dependency in graph.get(package, []):
            visit(dependency, depth + 1)

    visit("application")

    print(
        """
        Real applications often have transitive dependencies.

        Direct dependency:
            Your application -> web-framework

        Transitive dependency:
            Your application -> web-framework -> routing-library

        You usually declare the libraries your application directly depends on.
        The package manager resolves and installs their compatible dependencies.

        The larger the dependency graph becomes, the more important version
        constraints, testing, reproducibility, and security become.
        """
    )


# =============================================================================
# 13. PIP INSPECTION USING A TEMPORARY VENV
# =============================================================================

def run_command(
    command: list[str],
    *,
    check: bool = True,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command and return its completed-process object."""
    print("$", " ".join(command))

    return subprocess.run(
        command,
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
    )


def demonstrate_pip_in_temporary_environment() -> None:
    """Use pip against a real temporary venv without modifying global Python."""
    section("13. Inspecting pip inside an isolated environment")

    temporary_root = create_temporary_virtual_environment()

    try:
        environment_directory = temporary_root / ".venv"
        pip_command = virtual_environment_pip(environment_directory)

        version_result = run_command(
            pip_command + ["--version"],
            check=True,
        )
        print(version_result.stdout.strip())

        list_result = run_command(
            pip_command + ["list"],
            check=True,
        )
        print("\nInitial package list:")
        print(list_result.stdout.strip())

        check_result = run_command(
            pip_command + ["check"],
            check=True,
        )
        print("\nInitial dependency check:")
        print(check_result.stdout.strip())

    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)


# =============================================================================
# 14. INSTALLING A PACKAGE
# =============================================================================

def demonstrate_safe_package_installation() -> None:
    """
    Install a small real package into a temporary environment.

    The package is chosen because it is lightweight and useful for demonstrating
    packaging metadata. Network access may not be available in every execution
    environment, so installation failure is handled explicitly.
    """
    section("14. Installing a package into an isolated environment")

    temporary_root = create_temporary_virtual_environment()

    try:
        environment_directory = temporary_root / ".venv"
        python_path = virtual_environment_python(environment_directory)
        pip_command = virtual_environment_pip(environment_directory)

        package_name = "packaging"

        print(f"Attempting to install: {package_name}")

        result = run_command(
            pip_command + ["install", package_name],
            check=False,
        )

        if result.returncode != 0:
            print("Installation was not completed.")
            print("pip stderr:")
            print(result.stderr.strip())
            return

        print("Installation completed.")
        print(result.stdout.strip())

        imported = run_command(
            [
                str(python_path),
                "-c",
                "import packaging; print(packaging.__version__)",
            ],
            check=True,
        )

        print("Installed package version:", imported.stdout.strip())

        show_result = run_command(
            pip_command + ["show", package_name],
            check=True,
        )

        print("\nPackage metadata:")
        print(show_result.stdout.strip())

    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)


# =============================================================================
# 15. PIP FREEZE
# =============================================================================

def demonstrate_freeze() -> None:
    """Demonstrate exporting installed package versions."""
    section("15. pip freeze and environment snapshots")

    temporary_root = create_temporary_virtual_environment()

    try:
        environment_directory = temporary_root / ".venv"
        pip_command = virtual_environment_pip(environment_directory)

        result = run_command(
            pip_command + ["freeze"],
            check=True,
        )

        print("Frozen environment:")
        print(result.stdout.strip() or "(No third-party packages installed)")

        print(
            """
            `pip freeze` produces install-style package records for the
            environment. A common workflow is:

                python -m pip freeze > requirements.txt

            The resulting file can later be used with:

                python -m pip install -r requirements.txt

            Freezing is useful for reproducing an existing environment, but
            teams should understand whether the file represents direct
            application dependencies or a complete resolved environment.
            """
        )

    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)


# =============================================================================
# 16. PIP CHECK
# =============================================================================

def demonstrate_pip_check() -> None:
    """Show dependency consistency verification."""
    section("16. pip check")

    temporary_root = create_temporary_virtual_environment()

    try:
        environment_directory = temporary_root / ".venv"
        pip_command = virtual_environment_pip(environment_directory)

        result = run_command(
            pip_command + ["check"],
            check=False,
        )

        print("Exit code:", result.returncode)
        print("Output:", result.stdout.strip() or "(no output)")
        print("Errors:", result.stderr.strip() or "(no errors)")

        print(
            """
            `pip check` verifies whether installed distributions have compatible
            declared dependencies.

            A successful check does not prove that the application itself works.
            It only checks a particular class of dependency consistency.
            """
        )

    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)


# =============================================================================
# 17. REQUIREMENTS FILE GENERATION
# =============================================================================

def create_sample_requirements_file(directory: Path) -> Path:
    """Create an educational requirements file."""
    requirements_path = directory / "requirements.txt"

    requirements_path.write_text(
        textwrap.dedent(
            """
            # Direct runtime dependencies
            requests>=2.31,<3
            packaging>=24,<27

            # Development dependency
            pytest>=8,<9
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    return requirements_path


def demonstrate_requirements_file() -> None:
    """Create and inspect a real requirements.txt file."""
    section("17. Creating a requirements.txt file")

    with tempfile.TemporaryDirectory(prefix="requirements_demo_") as temporary_directory:
        directory = Path(temporary_directory)
        requirements_path = create_sample_requirements_file(directory)

        print(f"Created: {requirements_path}")
        print(requirements_path.read_text(encoding="utf-8"))

        print(
            """
            A project may separate dependency groups into multiple files, for
            example:

                requirements.txt
                requirements-dev.txt
                requirements-test.txt

            The exact organization depends on the project's architecture and
            deployment process.
            """
        )


# =============================================================================
# 18. DEPENDENCY DIRECT VS TRANSITIVE
# =============================================================================

def demonstrate_direct_and_transitive_dependencies() -> None:
    """Explain direct and transitive dependencies using a small graph."""
    section("18. Direct versus transitive dependencies")

    dependencies = {
        "my-application": ["framework"],
        "framework": ["router", "http-client"],
        "http-client": ["url-parser"],
        "router": [],
        "url-parser": [],
    }

    direct = dependencies["my-application"]

    discovered: set[str] = set()

    def collect(package: str) -> None:
        for dependency in dependencies.get(package, []):
            if dependency in discovered:
                continue

            discovered.add(dependency)
            collect(dependency)

    collect("my-application")

    print("Direct dependencies      :", direct)
    print("All transitive packages  :", sorted(discovered))

    print(
        """
        Direct dependencies are packages your project explicitly needs.

        Transitive dependencies are installed because one of your dependencies
        needs them.

        This distinction matters when maintaining requirements because adding
        every transitive package manually can make dependency maintenance more
        difficult.
        """
    )


# =============================================================================
# 19. EDITABLE INSTALLATIONS
# =============================================================================

def explain_editable_installation() -> None:
    """Explain pip's editable installation concept."""
    section("19. Editable installations")

    print(
        """
        A package can be installed in editable mode:

            python -m pip install -e .

        This is common during local development.

        Instead of copying the project's source into the environment as an
        ordinary installed package, the environment is configured so Python
        can import the project from its development location.

        Benefits:

            - source changes become immediately available
            - useful for package development
            - avoids repeated reinstallations during development

        Considerations:

            - it is primarily a development workflow
            - production deployment should use an appropriate built artifact
              or deployment mechanism
            - import behavior can differ from a conventional installation

        Modern Python packaging commonly uses pyproject.toml to describe
        package metadata and build configuration.
        """
    )


# =============================================================================
# 20. WHEELS AND SOURCE DISTRIBUTIONS
# =============================================================================

def explain_package_artifacts() -> None:
    """Explain common Python distribution formats."""
    section("20. Wheels and source distributions")

    print(
        """
        A Python package can be distributed in different artifact formats.

        Wheel:
            A built distribution designed for installation.

        Source distribution:
            An archive containing source and packaging metadata from which a
            build may be produced.

        Wheels are generally faster to install because they avoid some build
        steps.

        A wheel can be platform-specific, Python-version-specific, or
        architecture-specific depending on the package.

        Pure-Python wheels are usually more portable than wheels containing
        compiled native extensions.

        Native dependencies may introduce requirements such as:

            - compiler toolchains
            - operating-system libraries
            - architecture compatibility
            - compatible Python versions
        """
    )


# =============================================================================
# 21. PYPI AND PACKAGE INDEXES
# =============================================================================

def explain_package_indexes() -> None:
    """Explain package indexes and index configuration."""
    section("21. Python package indexes")

    print(
        """
        pip commonly retrieves packages from a Python package index.

        PyPI is the primary public package repository used by the Python
        ecosystem.

        Organizations may also operate private package indexes.

        Common concepts include:

            index-url
                Primary package index.

            extra-index-url
                Additional package index.

            trusted-host
                A security-sensitive setting that changes TLS trust behavior.

        Security principle:

            Do not blindly add arbitrary package indexes or trusted hosts.

        A dependency with the same project name on a different index can create
        supply-chain risks if index configuration is poorly designed.

        Prefer trusted sources, controlled configuration, and dependency
        verification appropriate to the organization's security model.
        """
    )


# =============================================================================
# 22. HASH PINNING
# =============================================================================

def demonstrate_hash_calculation() -> None:
    """Demonstrate how file hashes can identify exact artifacts."""
    section("22. Package hashes and artifact integrity")

    content = b"example package artifact content"

    digest = hashlib.sha256(content).hexdigest()

    print("Example artifact SHA-256:")
    print(digest)

    print(
        """
        A cryptographic hash can identify the exact bytes of a downloaded
        artifact.

        pip requirements can use hashes in environments where stronger
        artifact reproducibility and integrity controls are required.

        Hash verification is stronger than relying only on a package version,
        because one project version may be represented by different artifacts
        for different platforms or distribution formats.

        Hashes must be generated from trusted artifacts and maintained as part
        of a controlled dependency process.
        """
    )


# =============================================================================
# 23. ENVIRONMENT VARIABLES
# =============================================================================

def demonstrate_environment_variables() -> None:
    """Show how environment variables can identify environment configuration."""
    section("23. Environment variables and virtual environments")

    relevant_names = [
        "VIRTUAL_ENV",
        "PATH",
        "PYTHONPATH",
        "PIP_INDEX_URL",
        "PIP_EXTRA_INDEX_URL",
        "PIP_DISABLE_PIP_VERSION_CHECK",
    ]

    for name in relevant_names:
        value = os.environ.get(name)

        if name in {"PATH", "PYTHONPATH"} and value:
            display = value[:250] + ("..." if len(value) > 250 else "")
        else:
            display = value

        print(f"{name:30} = {display!r}")

    print(
        """
        VIRTUAL_ENV is commonly set when a shell activation script is active.

        PATH controls executable discovery.

        PYTHONPATH changes Python's module search path. It should be used
        cautiously because unexpected entries can cause confusing imports.

        pip also supports configuration through command-line options,
        environment variables, and configuration files.

        Sensitive credentials should not be placed directly into source code or
        committed configuration files.
        """
    )


# =============================================================================
# 24. IMPORT SEARCH PATH
# =============================================================================

def demonstrate_module_search_path() -> None:
    """Display the current Python module search path."""
    section("24. Python module search path")

    for index, entry in enumerate(sys.path, start=1):
        print(f"{index:02d}. {entry}")

    print(
        """
        Python searches sys.path when resolving imports.

        A virtual environment changes important path information so installed
        packages in that environment can be imported.

        Import problems often come from:

            - the wrong interpreter
            - the wrong virtual environment
            - conflicting local filenames
            - PYTHONPATH modifications
            - stale editable installations
            - multiple Python installations
        """
    )


# =============================================================================
# 25. WRONG INTERPRETER DIAGNOSTICS
# =============================================================================

def diagnose_python_command() -> None:
    """Provide practical interpreter diagnostics."""
    section("25. Diagnosing the wrong Python interpreter")

    print("Current executable:", sys.executable)

    if os.name == "nt":
        print(
            """
            On Windows, useful commands include:

                where python
                where pip
                py -0p

            The `py` launcher can list installed Python interpreters.
            """
        )
    else:
        print(
            """
            On Unix-like systems, useful commands include:

                which python
                which python3
                which pip
                which pip3
            """
        )

    print(
        """
        The most reliable Python-level diagnostic remains:

            python -c "import sys; print(sys.executable)"

        Compare that path with the expected .venv location.
        """
    )


# =============================================================================
# 26. COMMON VENV STRUCTURE
# =============================================================================

def show_expected_venv_structure() -> None:
    """Display a conceptual virtual-environment layout."""
    section("26. Typical virtual-environment structure")

    if os.name == "nt":
        structure = """
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
        """
    else:
        structure = """
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
        """

    print(textwrap.dedent(structure).strip())

    print(
        """
        The exact layout can vary by operating system and Python version.
        The environment directory should normally be treated as generated
        state rather than source code.
        """
    )


# =============================================================================
# 27. WHY .VENV IS USUALLY GITIGNORED
# =============================================================================

def demonstrate_gitignore_content() -> None:
    """Generate a conventional .gitignore fragment."""
    section("27. Why .venv should normally not be committed")

    gitignore = """
    .venv/
    venv/
    env/
    __pycache__/
    *.py[cod]
    """

    print(textwrap.dedent(gitignore).strip())

    print(
        """
        A virtual environment contains generated interpreter and package files.
        It is generally machine-specific and can be recreated from dependency
        specifications.

        Commit:

            source code
            dependency declarations
            configuration templates
            lock information when the chosen tooling uses it

        Usually do not commit:

            .venv/
            generated bytecode
            local caches
            machine-specific secrets
        """
    )


# =============================================================================
# 28. ENVIRONMENT RECREATION
# =============================================================================

def explain_recreation_workflow() -> None:
    """Explain a clean environment recreation process."""
    section("28. Recreating an environment")

    print(
        """
        A common reproducible workflow is:

            1. Install the intended Python version.
            2. Create a fresh virtual environment.
            3. Activate it or invoke its Python directly.
            4. Upgrade packaging tools when appropriate.
            5. Install declared dependencies.
            6. Run tests.
            7. Verify dependency consistency.
            8. Run the application.

        Example:

            python -m venv .venv

        Windows PowerShell:

            .venv\\Scripts\\Activate.ps1

        Linux/macOS:

            source .venv/bin/activate

        Then:

            python -m pip install -r requirements.txt
            python -m pip check
            python -m pytest

        The exact commands depend on the project's testing and packaging setup.
        """
    )


# =============================================================================
# 29. DEVELOPMENT VS PRODUCTION DEPENDENCIES
# =============================================================================

def explain_dependency_categories() -> None:
    """Explain runtime, development, testing, and optional dependencies."""
    section("29. Dependency categories")

    categories = {
        "Runtime": "Required for the application to operate.",
        "Development": "Useful while writing and maintaining the application.",
        "Testing": "Used for automated tests and test tooling.",
        "Linting": "Used to inspect code quality and style.",
        "Build": "Used to create distributable artifacts.",
        "Documentation": "Used to generate project documentation.",
        "Optional": "Required only for specific application features.",
    }

    for category, definition in categories.items():
        print(f"{category:15} {definition}")

    print(
        """
        Separating dependency categories reduces production environments and
        helps clarify why each package exists.

        For example, a web service might require a database driver at runtime
        while requiring pytest only in development and continuous integration.
        """
    )


# =============================================================================
# 30. ENVIRONMENT MARKERS
# =============================================================================

def explain_environment_markers() -> None:
    """Explain platform and Python-version-specific requirements."""
    section("30. Environment markers")

    examples = [
        'colorama; platform_system == "Windows"',
        'typing-extensions; python_version < "3.12"',
        'example-package; sys_platform == "linux"',
    ]

    for example in examples:
        print(example)

    print(
        """
        Environment markers allow dependency declarations to apply only under
        particular conditions.

        This is useful when a dependency is needed only on a particular
        operating system or Python version.

        Markers can involve information such as:

            python_version
            python_full_version
            platform_system
            sys_platform
            implementation_name
            platform_machine

        Marker expressions should be tested on every supported environment.
        """
    )


# =============================================================================
# 31. EXTRAS
# =============================================================================

def explain_optional_extras() -> None:
    """Explain package extras."""
    section("31. Optional dependency extras")

    print(
        """
        Some packages define optional feature groups called extras.

        Conceptual example:

            package[database]
            package[security]
            package[database,security]

        An extra allows a package author to define optional dependencies for a
        feature without forcing every user to install every optional library.

        Extras are useful when one package supports several integration modes.
        """
    )


# =============================================================================
# 32. PACKAGE NAME NORMALIZATION
# =============================================================================

def normalize_package_name(name: str) -> str:
    """
    Demonstrate the basic normalized form used by Python packaging names.

    PEP 503-style normalization treats runs of -, _, and . as equivalent and
    replaces them with a single hyphen, then lowercases the name.
    """
    return re.sub(r"[-_.]+", "-", name).lower()


def demonstrate_package_name_normalization() -> None:
    """Show that distribution names have normalization rules."""
    section("32. Package-name normalization")

    examples = [
        "Example_Package",
        "example-package",
        "example.package",
        "EXAMPLE--PACKAGE",
    ]

    for name in examples:
        print(f"{name:25} -> {normalize_package_name(name)}")

    print(
        """
        Distribution names and import names are not necessarily identical.

        For example, a package might be installed using a distribution name
        containing a hyphen while the Python import uses an underscore.

        Never assume:

            pip package name == import name

        Check the package documentation or metadata when uncertain.
        """
    )


# =============================================================================
# 33. PIP UNINSTALL
# =============================================================================

def demonstrate_uninstall_command() -> None:
    """Explain package removal."""
    section("33. Uninstalling packages")

    print(
        """
        Basic command:

            python -m pip uninstall package_name

        pip normally asks for confirmation interactively.

        Automated environments can use:

            python -m pip uninstall -y package_name

        Removing a direct dependency does not necessarily mean every related
        transitive dependency will be removed automatically.

        This is one reason a clean virtual environment is often easier to
        reproduce than trying to manually clean an old environment.
        """
    )


# =============================================================================
# 34. UPGRADE STRATEGIES
# =============================================================================

def explain_upgrade_strategies() -> None:
    """Explain controlled dependency upgrades."""
    section("34. Dependency upgrade strategies")

    print(
        """
        Uncontrolled upgrades can introduce breaking changes.

        Common strategies include:

            Conservative:
                Pin exact versions and upgrade intentionally.

            Range-based:
                Allow compatible versions within a tested range.

            Periodic:
                Review dependency updates on a scheduled basis.

            Automated:
                Use dependency update automation plus tests and review.

        A production project should balance:

            reproducibility
            security updates
            bug fixes
            compatibility
            maintenance effort

        A version pin is not a substitute for testing.
        """
    )


# =============================================================================
# 35. CONSTRAINT FILES
# =============================================================================

def explain_constraints() -> None:
    """Explain the purpose of pip constraints files."""
    section("35. Constraints files")

    print(
        """
        A constraints file can restrict versions without necessarily declaring
        those packages as direct dependencies.

        Conceptual example:

            requirements.txt
                web-framework
                database-driver

            constraints.txt
                shared-library==2.7.1

        Installation can use:

            python -m pip install -r requirements.txt -c constraints.txt

        Constraints are useful when an organization needs consistent versions
        across several dependency declarations.

        The distinction is important:

            requirements
                What should be installed.

            constraints
                Which versions are permitted when resolving dependencies.
        """
    )


# =============================================================================
# 36. BUILD ISOLATION
# =============================================================================

def explain_build_isolation() -> None:
    """Explain isolated build environments."""
    section("36. Build isolation")

    print(
        """
        Modern Python packaging can use isolated build environments.

        A project's build requirements can be specified in pyproject.toml.
        Packaging tools can then create a temporary environment containing the
        tools required to build the distribution.

        This prevents a developer's unrelated globally installed build tools
        from accidentally determining how a package is built.

        Build isolation is especially important for packages whose build system
        has its own dependencies.
        """
    )


# =============================================================================
# 37. PYPROJECT.TOML
# =============================================================================

def explain_pyproject_toml() -> None:
    """Explain modern Python project metadata at a conceptual level."""
    section("37. pyproject.toml")

    print(
        """
        pyproject.toml is a standardized configuration file used by modern
        Python packaging tools.

        It can contain:

            - project metadata
            - Python version requirements
            - runtime dependencies
            - optional dependencies
            - build-system configuration
            - tool-specific configuration

        Conceptual structure:

            [build-system]
            requires = ["setuptools", "wheel"]
            build-backend = "setuptools.build_meta"

            [project]
            name = "example-project"
            version = "1.0.0"
            dependencies = [
                "requests>=2.31"
            ]

        Exact fields and supported features depend on the packaging standards
        and chosen build backend.

        requirements.txt and pyproject.toml can coexist. They serve related but
        different purposes.
        """
    )


# =============================================================================
# 38. PYTHON VERSION CONSTRAINTS
# =============================================================================

def explain_python_version_requirements() -> None:
    """Explain interpreter compatibility."""
    section("38. Python-version requirements")

    print(
        """
        Dependency management includes both package versions and Python
        interpreter versions.

        A project may support:

            Python >=3.11,<3.14

        while a dependency may support a different range.

        Compatibility therefore requires solving constraints involving:

            Python version
            operating system
            CPU architecture
            direct packages
            transitive packages
            native libraries

        The environment should use an explicitly supported Python version,
        particularly for production systems.
        """
    )


# =============================================================================
# 39. REPRODUCIBILITY
# =============================================================================

def explain_reproducibility() -> None:
    """Explain different levels of reproducibility."""
    section("39. Reproducible environments")

    levels = [
        (
            "Weak",
            "Install packages without meaningful version constraints.",
        ),
        (
            "Moderate",
            "Declare direct dependencies with tested version ranges.",
        ),
        (
            "Strong",
            "Record a tested resolved dependency set.",
        ),
        (
            "Artifact-level",
            "Control exact package artifacts using hashes or an internal artifact repository.",
        ),
        (
            "Infrastructure-level",
            "Also control Python runtime, operating system, containers, and deployment configuration.",
        ),
    ]

    for level, description in levels:
        print(f"{level:18} {description}")

    print(
        """
        Reproducibility is not one binary property.

        A requirements file may reproduce package versions but still fail to
        reproduce the environment if:

            - Python versions differ
            - OS libraries differ
            - native extensions differ
            - environment variables differ
            - external services differ
            - architecture differs
        """
    )


# =============================================================================
# 40. TEMPORARY PROJECT DEMONSTRATION
# =============================================================================

def create_demo_project() -> Path:
    """Create a minimal temporary Python project."""
    root = Path(tempfile.mkdtemp(prefix="python_project_demo_"))

    (root / "src").mkdir()
    (root / "tests").mkdir()

    (root / "src" / "calculator.py").write_text(
        textwrap.dedent(
            """
            def add(left: int, right: int) -> int:
                return left + right
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    (root / "tests" / "test_calculator.py").write_text(
        textwrap.dedent(
            """
            from src.calculator import add

            def test_add():
                assert add(2, 3) == 5
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    return root


def demonstrate_project_structure() -> None:
    """Show a clean project structure using a virtual environment."""
    section("40. Example project structure")

    root = create_demo_project()

    try:
        environment_directory = root / ".venv"
        environment_directory.mkdir()

        files = [
            root / "src" / "calculator.py",
            root / "tests" / "test_calculator.py",
            root / "requirements.txt",
            root / ".gitignore",
        ]

        (root / "requirements.txt").write_text(
            "pytest>=8,<9\n",
            encoding="utf-8",
        )

        (root / ".gitignore").write_text(
            ".venv/\n__pycache__/\n.pytest_cache/\n",
            encoding="utf-8",
        )

        print(f"{root.name}/")
        print("├── .venv/")
        print("├── src/")
        print("│   └── calculator.py")
        print("├── tests/")
        print("│   └── test_calculator.py")
        print("├── requirements.txt")
        print("└── .gitignore")

        print("\nCreated files:")
        for file_path in files:
            print(f"  {file_path.relative_to(root)}")

    finally:
        shutil.rmtree(root, ignore_errors=True)


# =============================================================================
# 41. SUBPROCESS AND ENVIRONMENT CONTROL
# =============================================================================

def demonstrate_explicit_environment_execution() -> None:
    """Run a Python command through an explicitly selected environment."""
    section("41. Explicitly running a command inside a venv")

    temporary_root = create_temporary_virtual_environment()

    try:
        environment_directory = temporary_root / ".venv"
        python_path = virtual_environment_python(environment_directory)

        code = """
import sys
print("Python executable:", sys.executable)
print("Prefix:", sys.prefix)
print("Base prefix:", sys.base_prefix)
"""

        result = run_command(
            [str(python_path), "-c", textwrap.dedent(code)],
            check=True,
        )

        print(result.stdout.strip())

        print(
            """
            This pattern is valuable in automation because it does not depend
            on interactive shell activation.

            CI systems and deployment scripts often explicitly select the
            intended interpreter or environment.
            """
        )

    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)


# =============================================================================
# 42. SECURITY: SUPPLY CHAIN
# =============================================================================

def explain_security() -> None:
    """Explain package-management security considerations."""
    section("42. Security considerations")

    print(
        """
        Python dependency management is also a software supply-chain problem.

        Important risks include:

            Malicious packages
                A package can contain harmful code.

            Typosquatting
                A malicious package may use a name similar to a legitimate one.

            Dependency confusion
                An internal package name can accidentally resolve to an
                untrusted public package.

            Compromised maintainers
                A legitimate package can be compromised.

            Vulnerable dependencies
                A package may contain a known security flaw.

            Malicious installation scripts
                Package installation can execute build or installation logic.

        Defensive practices include:

            - use trusted package sources
            - review dependencies
            - keep dependencies maintained
            - use vulnerability scanning appropriate to the organization
            - control private indexes
            - verify artifacts where appropriate
            - minimize unnecessary dependencies
            - use lock or pinning mechanisms where appropriate
            - test upgrades before production deployment
            - never commit package credentials or tokens

        Installing a package is equivalent to granting code from that package
        significant execution privileges inside the environment. Dependency
        selection therefore deserves the same engineering discipline as source
        code selection.
        """
    )


# =============================================================================
# 43. SECURITY: SECRETS
# =============================================================================

def demonstrate_secret_safe_configuration() -> None:
    """Show the difference between source-controlled configuration and secrets."""
    section("43. Secrets and environment configuration")

    unsafe_example = """
    DATABASE_PASSWORD = "my-real-password"
    """

    safe_concept = """
    DATABASE_PASSWORD = os.environ["DATABASE_PASSWORD"]
    """

    print("Unsafe pattern:")
    print(textwrap.dedent(unsafe_example).strip())

    print("\nSafer conceptual pattern:")
    print(textwrap.dedent(safe_concept).strip())

    print(
        """
        Secrets should normally be supplied through a secure configuration
        mechanism appropriate to the deployment environment.

        Do not place real credentials in:

            requirements.txt
            source code
            README files
            .gitignore comments
            shell history
            public package metadata
        """
    )


# =============================================================================
# 44. PERFORMANCE
# =============================================================================

def explain_performance() -> None:
    """Explain package-management performance considerations."""
    section("44. Performance considerations")

    print(
        """
        Virtual environments are lightweight compared with full virtual
        machines because they primarily isolate Python-level dependencies.

        Installation performance depends on:

            - package size
            - network speed
            - package cache state
            - wheel availability
            - native compilation
            - dependency graph size
            - package index performance

        Wheels can substantially reduce installation time compared with building
        packages from source.

        Reusing a controlled package cache can improve CI performance, but cache
        invalidation must be handled carefully so stale or incompatible artifacts
        are not reused incorrectly.
        """
    )


# =============================================================================
# 45. WINDOWS EXECUTION POLICY
# =============================================================================

def explain_windows_activation_issue() -> None:
    """Explain a common Windows PowerShell activation issue."""
    section("45. Windows PowerShell activation issues")

    print(
        """
        On Windows, PowerShell may restrict execution of scripts according to
        its execution-policy configuration.

        A common symptom is that:

            .venv\\Scripts\\Activate.ps1

        cannot be executed.

        This is a shell-policy issue, not necessarily a broken Python
        environment.

        An alternative is to avoid activation and directly execute:

            .venv\\Scripts\\python.exe -m pip --version

        This explicitly selects the environment and can be useful when shell
        policy prevents activation.

        Security-sensitive systems should follow their organization's PowerShell
        execution-policy requirements rather than weakening policy casually.
        """
    )


# =============================================================================
# 46. LINUX/MAC ACTIVATION ISSUE
# =============================================================================

def explain_unix_permissions() -> None:
    """Explain common Unix activation and execution considerations."""
    section("46. Unix-like activation and permissions")

    print(
        """
        On Linux and macOS, activation usually uses:

            source .venv/bin/activate

        If the environment was created correctly, its Python executable should
        be executable.

        When diagnosing problems, inspect:

            ls -la .venv/bin/
            .venv/bin/python --version
            .venv/bin/python -m pip --version

        Running the environment's interpreter directly avoids ambiguity about
        shell PATH resolution.
        """
    )


# =============================================================================
# 47. DELETING A VIRTUAL ENVIRONMENT
# =============================================================================

def demonstrate_environment_recreation_by_deletion() -> None:
    """Show that a venv can be discarded and recreated."""
    section("47. Deleting and recreating a virtual environment")

    root = Path(tempfile.mkdtemp(prefix="recreate_venv_demo_"))

    try:
        environment_directory = root / ".venv"

        venv.EnvBuilder(with_pip=True).create(environment_directory)

        print("Created:", environment_directory.exists())

        shutil.rmtree(environment_directory)

        print("Deleted:", not environment_directory.exists())

        venv.EnvBuilder(with_pip=True).create(environment_directory)

        print("Recreated:", environment_directory.exists())

    finally:
        shutil.rmtree(root, ignore_errors=True)

    print(
        """
        This illustrates an important property of virtual environments:

        They are disposable.

        If an environment becomes inconsistent, rebuilding it from a controlled
        dependency specification is often safer than manually repairing dozens
        of installed packages.
        """
    )


# =============================================================================
# 48. IMPORT CONFLICT EXAMPLE
# =============================================================================

def demonstrate_local_module_shadowing() -> None:
    """Demonstrate a subtle import problem unrelated to pip."""
    section("48. Import shadowing and misleading package errors")

    with tempfile.TemporaryDirectory(prefix="import_shadow_demo_") as temporary_directory:
        root = Path(temporary_directory)

        fake_module = root / "json.py"
        fake_module.write_text(
            "value = 'This is a local module, not the standard-library json module.'\n",
            encoding="utf-8",
        )

        print("Created local file:", fake_module)

        print(
            """
            A file named after a standard-library or third-party module can
            shadow the intended package.

            Examples of risky filenames:

                json.py
                requests.py
                pandas.py
                typing.py
                random.py

            If imports behave strangely, inspect the module location:

                import package_name
                print(package_name.__file__)

            Not every import problem is a dependency-installation problem.
            """
        )


# =============================================================================
# 49. PYTHONPATH EDGE CASE
# =============================================================================

def demonstrate_pythonpath_risk() -> None:
    """Explain why PYTHONPATH can complicate isolation."""
    section("49. PYTHONPATH and isolation")

    original = os.environ.get("PYTHONPATH")

    try:
        os.environ["PYTHONPATH"] = "/example/external/path"

        print("Temporary PYTHONPATH:", os.environ["PYTHONPATH"])

        print(
            """
            PYTHONPATH can insert external directories into Python's import
            search path.

            This can undermine assumptions about where a module comes from.

            For clean application environments, avoid unnecessary PYTHONPATH
            modifications and prefer packaging the project properly.
            """
        )

    finally:
        if original is None:
            os.environ.pop("PYTHONPATH", None)
        else:
            os.environ["PYTHONPATH"] = original


# =============================================================================
# 50. CI/CD
# =============================================================================

def explain_ci_cd_dependency_workflow() -> None:
    """Explain dependency management in continuous integration."""
    section("50. CI/CD dependency workflow")

    print(
        """
        A robust CI workflow commonly follows this sequence:

            checkout source
                |
                v
            select supported Python
                |
                v
            create isolated environment
                |
                v
            install declared dependencies
                |
                v
            run dependency validation
                |
                v
            run tests
                |
                v
            build artifacts
                |
                v
            deploy only validated artifacts

        The exact implementation varies by CI platform.

        CI should avoid depending on packages accidentally installed on the
        runner outside the project's declared environment.
        """
    )


# =============================================================================
# 51. DOCKER VS VENV
# =============================================================================

def compare_venv_and_docker() -> None:
    """Compare Python virtual environments with containers."""
    section("51. Virtual environments versus containers")

    comparison = [
        ("Primary purpose", "Python package isolation", "OS/process environment isolation"),
        ("Isolation level", "Python environment", "Broader process/filesystem/network boundary"),
        ("Startup cost", "Very low", "Higher than a simple venv"),
        ("Replaces Python?", "No", "Often packages the runtime with the application"),
        ("Dependency control", "Strong at Python-package level", "Strong at image/environment level"),
        ("Typical use", "Local development, tests, applications", "Deployment, CI, services"),
    ]

    print(f"{'Aspect':25} {'venv':35} {'Container':35}")
    print("-" * 95)

    for aspect, venv_value, container_value in comparison:
        print(f"{aspect:25} {venv_value:35} {container_value:35}")

    print(
        """
        They are not mutually exclusive.

        A containerized Python application can still use a virtual environment,
        although many container workflows deliberately rely on the container
        itself as the primary isolation boundary.

        The correct choice depends on the deployment architecture.
        """
    )


# =============================================================================
# 52. VENV VS GLOBAL INSTALLATION
# =============================================================================

def compare_global_and_virtual_installation() -> None:
    """Compare global package installation with virtual environments."""
    section("52. Global installation versus virtual environments")

    comparison = [
        ("Isolation", "Low", "High"),
        ("Project independence", "Low", "High"),
        ("Ease of quick experiments", "High", "High"),
        ("Risk of version conflicts", "Higher", "Lower"),
        ("Reproducibility", "Poorer", "Better"),
        ("Recommended for applications", "Usually no", "Usually yes"),
    ]

    print(f"{'Property':30} {'Global':20} {'Virtual environment':25}")
    print("-" * 78)

    for property_name, global_value, venv_value in comparison:
        print(
            f"{property_name:30} "
            f"{global_value:20} "
            f"{venv_value:25}"
        )


# =============================================================================
# 53. SYSTEM PYTHON WARNING
# =============================================================================

def explain_system_python() -> None:
    """Explain why modifying OS-managed Python can be dangerous."""
    section("53. System-managed Python")

    print(
        """
        Some operating systems use Python for system utilities or package
        management.

        Installing arbitrary packages into an OS-managed Python can interfere
        with system software or package-manager assumptions.

        Prefer:

            project virtual environments
            operating-system package managers for OS components
            controlled application runtimes for production

        Avoid using administrative privileges merely to make pip installation
        succeed.
        """
    )


# =============================================================================
# 54. EXTERNALLY MANAGED ENVIRONMENTS
# =============================================================================

def explain_externally_managed_python() -> None:
    """Explain the externally-managed-environment concept."""
    section("54. Externally managed Python environments")

    print(
        """
        Modern Python packaging standards allow an environment to indicate that
        it is managed by an external system.

        pip may refuse a direct global installation and display an
        externally-managed-environment error.

        This is intentional protection against modifying an environment owned by
        an operating-system package manager.

        The usual solution for application dependencies is to create a virtual
        environment and install packages there.

        Do not bypass the protection blindly just because pip reports an error.
        """
    )


# =============================================================================
# 55. PIP CACHE
# =============================================================================

def explain_pip_cache() -> None:
    """Explain package caching."""
    section("55. pip cache")

    print(
        """
        pip can maintain a local cache of downloaded or built artifacts.

        Useful diagnostic commands include:

            python -m pip cache info
            python -m pip cache list
            python -m pip cache purge

        Caching can make repeated installations faster.

        In CI, caches should be keyed carefully around relevant variables such
        as Python version, operating system, architecture, dependency state, and
        package-manager configuration.
        """
    )


# =============================================================================
# 56. OFFLINE INSTALLATION
# =============================================================================

def explain_offline_installation() -> None:
    """Explain a controlled offline installation pattern."""
    section("56. Offline and controlled installation")

    print(
        """
        Packages can be downloaded ahead of time:

            python -m pip download -r requirements.txt -d packages/

        Then installation can be performed from local artifacts:

            python -m pip install --no-index --find-links=packages/ -r requirements.txt

        This pattern can support restricted or offline environments.

        The downloaded artifacts should come from a trusted and controlled
        process. Offline installation does not automatically guarantee security.
        """
    )


# =============================================================================
# 57. DEPENDENCY AUDIT CONCEPT
# =============================================================================

def explain_dependency_auditing() -> None:
    """Explain the purpose of dependency auditing without requiring external tools."""
    section("57. Dependency auditing")

    print(
        """
        Dependency auditing asks questions such as:

            - Which packages are installed?
            - Which versions are installed?
            - Which dependencies are direct?
            - Which are transitive?
            - Are any versions known to be vulnerable?
            - Which packages are no longer required?
            - Which licenses apply?
            - Which packages execute native code?
            - Which packages are obtained from which source?

        `python -m pip list`, `python -m pip show`, and
        `python -m pip freeze` provide basic inventory information.

        Security-focused organizations commonly add specialized dependency
        scanners, artifact controls, software composition analysis, and
        vulnerability-management processes.
        """
    )


# =============================================================================
# 58. DEPENDENCY BLOAT
# =============================================================================

def explain_dependency_bloat() -> None:
    """Explain why unnecessary dependencies are undesirable."""
    section("58. Dependency bloat")

    print(
        """
        Every additional dependency can introduce:

            - maintenance work
            - installation time
            - security exposure
            - transitive dependencies
            - licensing considerations
            - compatibility constraints
            - larger deployment artifacts

        Prefer a focused dependency set.

        Do not add a large framework when a small standard-library component is
        sufficient for a simple requirement.
        """
    )


# =============================================================================
# 59. BREAKING CHANGES
# =============================================================================

def explain_breaking_changes() -> None:
    """Explain semantic-versioning assumptions and limitations."""
    section("59. Breaking changes and semantic versioning")

    print(
        """
        Semantic versioning commonly uses:

            MAJOR.MINOR.PATCH

        where projects often intend:

            MAJOR
                potentially breaking API changes

            MINOR
                backward-compatible features

            PATCH
                backward-compatible fixes

        This is a convention, not a universal guarantee.

        A package can introduce breaking behavior without following semantic
        versioning perfectly, and different projects may define compatibility
        differently.

        Therefore version constraints should be combined with testing.
        """
    )


# =============================================================================
# 60. DEPENDENCY LOCKING
# =============================================================================

def explain_locking() -> None:
    """Explain dependency locking at a conceptual level."""
    section("60. Dependency locking")

    print(
        """
        A lock file records a resolved dependency set so repeated installations
        can use the same intended versions and, depending on the tooling,
        artifacts.

        Locking is particularly useful for applications where reproducible
        deployments are important.

        requirements.txt can be used as a pinned environment snapshot, but the
        Python ecosystem also contains dedicated tools and workflows for
        dependency locking and resolution.

        The important architectural distinction is:

            dependency declaration
                What the project requires.

            dependency resolution
                Which concrete versions satisfy all constraints.

            lock state
                Which resolved dependency set should be reproduced.
        """
    )


# =============================================================================
# 61. PACKAGE METADATA
# =============================================================================

def demonstrate_importlib_metadata() -> None:
    """Use the standard library to inspect installed distribution metadata."""
    section("61. Inspecting installed distribution metadata")

    try:
        from importlib import metadata

        distributions = list(metadata.distributions())

        print("Number of visible installed distributions:", len(distributions))

        for distribution in sorted(
            distributions,
            key=lambda item: (item.metadata.get("Name") or "").lower(),
        )[:10]:
            name = distribution.metadata.get("Name")
            version = distribution.version
            print(f"  {name} == {version}")

    except Exception as exc:
        print("Metadata inspection failed:", exc)

    print(
        """
        importlib.metadata is part of Python's standard library in modern
        Python versions and provides access to installed distribution metadata.

        This demonstrates an important distinction:

            import package
                concerns importable Python modules.

            distribution metadata
                concerns installed package distributions.

        A distribution can expose one or more import packages.
        """
    )


# =============================================================================
# 62. VERSION DISCOVERY
# =============================================================================

def demonstrate_package_version_lookup() -> None:
    """Demonstrate version lookup without importing the package itself."""
    section("62. Looking up an installed package version")

    try:
        from importlib.metadata import version, PackageNotFoundError

        package_name = "packaging"

        try:
            installed_version = version(package_name)
            print(f"{package_name} version:", installed_version)
        except PackageNotFoundError:
            print(f"{package_name!r} is not installed in this environment.")

    except ImportError:
        print("importlib.metadata is unavailable on this Python version.")


# =============================================================================
# 63. EXCEPTION HANDLING
# =============================================================================

def demonstrate_pip_error_handling() -> None:
    """Show how automation should handle pip failures."""
    section("63. Handling pip failures in automation")

    fake_command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "__package_that_should_not_exist_for_this_demo__",
    ]

    result = subprocess.run(
        fake_command,
        capture_output=True,
        text=True,
        check=False,
    )

    print("Exit code:", result.returncode)

    if result.returncode == 0:
        print("Unexpectedly succeeded.")
    else:
        print("Expected installation failure captured safely.")
        print("stderr preview:")
        print(result.stderr[:600])

    print(
        """
        Automation should inspect exit codes.

        `check=True` raises subprocess.CalledProcessError for a non-zero exit
        code.

        `check=False` allows the program to inspect the result manually.

        Never assume that a package installation succeeded merely because the
        command was launched.
        """
    )


# =============================================================================
# 64. PYTHON VERSION CHECK
# =============================================================================

def validate_python_version(
    minimum: tuple[int, int],
    maximum_exclusive: tuple[int, int] | None = None,
) -> bool:
    """Validate the running interpreter's major/minor version."""
    current = sys.version_info[:2]

    if current < minimum:
        return False

    if maximum_exclusive is not None and current >= maximum_exclusive:
        return False

    return True


def demonstrate_python_version_validation() -> None:
    """Demonstrate application-level interpreter compatibility checks."""
    section("64. Validating Python interpreter compatibility")

    supported = validate_python_version(
        minimum=(3, 10),
        maximum_exclusive=(4, 0),
    )

    print("Current Python:", platform.python_version())
    print("Supported:", supported)

    print(
        """
        Package metadata should normally declare supported Python versions so
        package installers can resolve compatible distributions.

        Application-level checks can still be useful for explicit runtime
        diagnostics, but should not replace proper packaging metadata.
        """
    )


# =============================================================================
# 65. MULTIPLE ENVIRONMENTS
# =============================================================================

def demonstrate_multiple_environments() -> None:
    """Create separate temporary environments to demonstrate isolation."""
    section("65. Multiple isolated environments")

    roots: list[Path] = []

    try:
        for label in ("project_a", "project_b"):
            root = Path(tempfile.mkdtemp(prefix=f"{label}_"))
            roots.append(root)

            environment_directory = root / ".venv"
            venv.EnvBuilder(with_pip=True).create(environment_directory)

            python_path = virtual_environment_python(environment_directory)

            result = run_command(
                [
                    str(python_path),
                    "-c",
                    "import sys; print(sys.executable); print(sys.prefix)",
                ],
                check=True,
            )

            print(f"\n{label}:")
            print(result.stdout.strip())

        print(
            """
            Each environment has a different location.

            Packages installed into one environment do not automatically become
            installed into the other environment.
            """
        )

    finally:
        for root in roots:
            shutil.rmtree(root, ignore_errors=True)


# =============================================================================
# 66. ENVIRONMENT REPAIR
# =============================================================================

def explain_repair_strategy() -> None:
    """Explain when recreation is preferable to manual repair."""
    section("66. Repairing a broken environment")

    print(
        """
        If a development environment becomes inconsistent, possible approaches
        include:

            1. Inspect:
                   python -m pip check
                   python -m pip list

            2. Identify the expected dependency specification.

            3. Compare the actual environment with the expected environment.

            4. Reinstall or rebuild if necessary.

        If the environment is disposable, deleting .venv and recreating it is
        often the cleanest option.

        Do not manually copy site-packages directories between Python
        environments. Compiled extensions and interpreter-specific files can
        make such copying unreliable.
        """
    )


# =============================================================================
# 67. RELATIVE PATHS AND PROJECT ROOTS
# =============================================================================

def demonstrate_path_resolution() -> None:
    """Show why pathlib is useful for project-oriented automation."""
    section("67. Project paths and pathlib")

    project_root = Path.cwd()
    environment_directory = project_root / ".venv"
    requirements_path = project_root / "requirements.txt"

    print("Current directory :", project_root)
    print("Expected venv     :", environment_directory)
    print("Requirements file  :", requirements_path)

    print(
        """
        pathlib makes project-path construction explicit and cross-platform.

        Avoid hard-coding separators such as:

            project + "/" + ".venv"

        Prefer:

            Path(project) / ".venv"

        This is especially important in scripts that must run on both Windows
        and Unix-like systems.
        """
    )


# =============================================================================
# 68. ENVIRONMENT BOOTSTRAP SCRIPT
# =============================================================================

def bootstrap_project_environment(
    project_directory: Path,
    requirements_file: Path | None = None,
) -> None:
    """
    Demonstrate a complete environment bootstrap process.

    This function creates a venv and optionally installs requirements. It is not
    automatically executed against the user's project, preventing accidental
    modifications.
    """
    section("68. Programmatic project-environment bootstrap")

    environment_directory = project_directory / ".venv"

    print("Project:", project_directory)
    print("Environment:", environment_directory)

    if environment_directory.exists():
        print("Environment already exists.")
        return

    venv.EnvBuilder(with_pip=True).create(environment_directory)

    print("Environment created.")

    if requirements_file is not None:
        python_path = virtual_environment_python(environment_directory)

        result = subprocess.run(
            [
                str(python_path),
                "-m",
                "pip",
                "install",
                "-r",
                str(requirements_file),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        print("Dependency installation exit code:", result.returncode)

        if result.returncode != 0:
            print(result.stderr)


# =============================================================================
# 69. PACKAGE AVAILABILITY
# =============================================================================

def package_is_importable(package_name: str) -> bool:
    """Return whether Python can find a module by name."""
    return importlib.util.find_spec(package_name) is not None


def demonstrate_package_detection() -> None:
    """Demonstrate module availability checks."""
    section("69. Detecting package availability")

    candidates = [
        "json",
        "pathlib",
        "hashlib",
        "packaging",
        "definitely_not_a_real_module",
    ]

    for package_name in candidates:
        print(
            f"{package_name:35} "
            f"{package_is_importable(package_name)}"
        )

    print(
        """
        This checks importability, not whether a distribution satisfies a
        particular version requirement.

        For installed distribution metadata, use importlib.metadata or pip.
        """
    )


# =============================================================================
# 70. COMMON MISTAKES
# =============================================================================

def explain_common_mistakes() -> None:
    """List practical mistakes and corrections."""
    section("70. Common mistakes")

    mistakes = [
        (
            "Installing everything globally",
            "Create a project-specific virtual environment.",
        ),
        (
            "Using pip from the wrong Python",
            "Use python -m pip and inspect sys.executable.",
        ),
        (
            "Committing .venv",
            "Ignore the environment and commit dependency specifications.",
        ),
        (
            "Using an unbounded dependency",
            "Use a tested compatibility range when appropriate.",
        ),
        (
            "Assuming pip freeze is a dependency design tool",
            "Distinguish direct declarations from resolved environment state.",
        ),
        (
            "Ignoring Python-version compatibility",
            "Declare and test supported Python versions.",
        ),
        (
            "Disabling security protections casually",
            "Understand why the protection exists before changing configuration.",
        ),
        (
            "Copying site-packages between machines",
            "Recreate the environment from controlled dependency data.",
        ),
        (
            "Assuming package name equals import name",
            "Inspect package metadata or documentation.",
        ),
        (
            "Never rebuilding old environments",
            "Use disposable environments and automated recreation.",
        ),
    ]

    for mistake, correction in mistakes:
        print(f"\nMistake:   {mistake}")
        print(f"Better:    {correction}")


# =============================================================================
# 71. EDGE CASES
# =============================================================================

def explain_edge_cases() -> None:
    """Explain important virtual-environment edge cases."""
    section("71. Edge cases")

    print(
        """
        1. Multiple Python installations
           A machine can have several interpreters. Always identify the exact
           interpreter used by the project.

        2. Python upgraded or removed
           An old virtual environment may depend on a Python executable that
           no longer exists. Recreate the environment using the supported
           interpreter.

        3. Native extensions
           A package compiled for one Python version or architecture may not
           work in another environment.

        4. Operating-system differences
           A frozen dependency set may still require different wheels or native
           system libraries on different platforms.

        5. Shell activation
           Activation scripts differ between PowerShell, cmd.exe, bash, zsh,
           and other shells.

        6. Existing .venv
           `python -m venv .venv` can modify or recreate an existing environment.
           Understand the intended state before doing so.

        7. Network restrictions
           pip may be unable to reach package indexes. Offline installation
           requires pre-downloaded trusted artifacts.

        8. Private dependencies
           Authentication and package-index configuration must be handled
           securely.

        9. Local package development
           Editable installs may produce behavior different from a wheel-based
           production installation.

        10. System-managed Python
            Operating-system packaging rules may intentionally block global pip
            installation.
        """
    )


# =============================================================================
# 72. BEST PRACTICES
# =============================================================================

def explain_best_practices() -> None:
    """Provide a consolidated set of practical practices."""
    section("72. Best practices")

    practices = [
        "Create one isolated environment per project or independently managed application.",
        "Use a clearly supported Python version.",
        "Use `python -m pip` when selecting the interpreter explicitly.",
        "Keep .venv outside version control.",
        "Declare direct dependencies intentionally.",
        "Use compatible version ranges or pins according to project requirements.",
        "Test dependency upgrades.",
        "Recreate environments instead of endlessly repairing them.",
        "Run `python -m pip check` during validation.",
        "Use CI to test a clean environment.",
        "Minimize unnecessary dependencies.",
        "Control package indexes and private repositories.",
        "Treat dependencies as executable third-party code.",
        "Protect package credentials and secrets.",
        "Use hashes or stronger artifact controls when required.",
        "Document supported Python versions.",
        "Keep development and runtime dependencies appropriately separated.",
        "Use build isolation and modern packaging metadata for distributable packages.",
    ]

    for number, practice in enumerate(practices, start=1):
        print(f"{number:02d}. {practice}")


# =============================================================================
# 73. END-TO-END SIMULATION
# =============================================================================

def demonstrate_end_to_end_workflow() -> None:
    """
    Simulate a complete isolated project setup.

    The example uses packaging as a lightweight third-party dependency and
    avoids modifying the user's global Python installation.
    """
    section("73. End-to-end virtual-environment workflow")

    root = Path(tempfile.mkdtemp(prefix="end_to_end_project_"))

    try:
        environment_directory = root / ".venv"
        requirements_path = root / "requirements.txt"

        requirements_path.write_text(
            "packaging>=24,<27\n",
            encoding="utf-8",
        )

        print("1. Project created:", root)

        venv.EnvBuilder(with_pip=True).create(environment_directory)
        print("2. Virtual environment created.")

        python_path = virtual_environment_python(environment_directory)

        python_version = run_command(
            [str(python_path), "--version"],
            check=True,
        )
        print("3. Python:", python_version.stdout.strip())

        install_result = run_command(
            [
                str(python_path),
                "-m",
                "pip",
                "install",
                "-r",
                str(requirements_path),
            ],
            check=False,
        )

        if install_result.returncode != 0:
            print("4. Installation could not complete.")
            print(install_result.stderr.strip())
            return

        print("4. Requirements installed.")

        check_result = run_command(
            [str(python_path), "-m", "pip", "check"],
            check=True,
        )
        print("5. pip check:", check_result.stdout.strip() or "No broken requirements.")

        package_version = run_command(
            [
                str(python_path),
                "-c",
                "from importlib.metadata import version; print(version('packaging'))",
            ],
            check=True,
        )
        print("6. Installed packaging version:", package_version.stdout.strip())

        print("7. Environment can now be discarded and recreated from requirements.txt.")

    finally:
        shutil.rmtree(root, ignore_errors=True)


# =============================================================================
# 74. DECISION GUIDE
# =============================================================================

def dependency_management_decision_guide() -> None:
    """Provide a concise decision framework."""
    section("74. Dependency-management decision guide")

    print(
        """
        Need project isolation?
            -> Create a venv.

        Need to install a package?
            -> Use python -m pip install.

        Need to inspect installed packages?
            -> Use python -m pip list or pip show.

        Need an environment snapshot?
            -> Use python -m pip freeze.

        Need to install declared dependencies?
            -> Use python -m pip install -r requirements.txt.

        Need to verify dependency consistency?
            -> Use python -m pip check.

        Need a modern package project definition?
            -> Consider pyproject.toml.

        Need controlled resolved versions?
            -> Use an appropriate locking or constraints strategy.

        Need production isolation beyond Python packages?
            -> Consider containers or another deployment isolation mechanism.

        Need stronger supply-chain controls?
            -> Use trusted indexes, artifact verification, scanning, controlled
               dependency updates, and appropriate lock/hash mechanisms.
        """
    )


# =============================================================================
# 75. MINI TEST SUITE
# =============================================================================

def run_internal_tests() -> None:
    """Run assertions covering the educational helper functions."""
    section("75. Internal self-tests")

    assert normalize_package_name("Example_Package") == "example-package"
    assert normalize_package_name("example.package") == "example-package"

    version = Version.parse("2.3.4")
    assert str(version) == "2.3.4"

    assert version_satisfies(
        Version.parse("2.3.4"),
        ">=",
        Version.parse("2.0.0"),
    )

    assert not version_satisfies(
        Version.parse("1.9.9"),
        ">=",
        Version.parse("2.0.0"),
    )

    assert parse_requirement_line("requests==2.32.3") == (
        "requests",
        "==",
        "2.32.3",
    )

    assert parse_requirement_line("# comment") is None
    assert parse_requirement_line("") is None

    print("All internal assertions passed.")


# =============================================================================
# 76. MAIN PROGRAM
# =============================================================================

def main() -> None:
    """
    Execute the complete tutorial.

    The demonstrations intentionally avoid making permanent changes to the
    user's global Python environment. Temporary virtual environments are
    created where real pip/venv behavior needs to be demonstrated.
    """
    section("Python Virtual Environments: pip, venv, requirements.txt, dependency management")

    explain_python_installation()
    inspect_current_python()
    demonstrate_standard_library_vs_external_package()
    demonstrate_dependency_conflict()

    demonstrate_real_venv_creation()
    explain_activation()
    explain_python_m_pip()
    explain_pip_commands()
    explain_requirements_file()
    demonstrate_requirement_parser()
    demonstrate_version_comparison()
    dependency_graph_demo()

    demonstrate_pip_in_temporary_environment()
    demonstrate_safe_package_installation()
    demonstrate_freeze()
    demonstrate_pip_check()
    demonstrate_requirements_file()
    demonstrate_direct_and_transitive_dependencies()

    explain_editable_installation()
    explain_package_artifacts()
    explain_package_indexes()
    demonstrate_hash_calculation()
    demonstrate_environment_variables()
    demonstrate_module_search_path()
    diagnose_python_command()
    show_expected_venv_structure()
    demonstrate_gitignore_content()
    explain_recreation_workflow()

    explain_dependency_categories()
    explain_environment_markers()
    explain_optional_extras()
    demonstrate_package_name_normalization()
    demonstrate_uninstall_command()
    explain_upgrade_strategies()
    explain_constraints()
    explain_build_isolation()
    explain_pyproject_toml()
    explain_python_version_requirements()

    explain_reproducibility()
    demonstrate_project_structure()
    demonstrate_explicit_environment_execution()

    explain_security()
    demonstrate_secret_safe_configuration()
    explain_performance()
    explain_windows_activation_issue()
    explain_unix_permissions()

    demonstrate_environment_recreation_by_deletion()
    demonstrate_local_module_shadowing()
    demonstrate_pythonpath_risk()

    explain_ci_cd_dependency_workflow()
    compare_venv_and_docker()
    compare_global_and_virtual_installation()
    explain_system_python()
    explain_externally_managed_python()
    explain_pip_cache()
    explain_offline_installation()
    explain_dependency_auditing()
    explain_dependency_bloat()
    explain_breaking_changes()
    explain_locking()

    demonstrate_importlib_metadata()
    demonstrate_package_version_lookup()
    demonstrate_pip_error_handling()
    demonstrate_python_version_validation()
    demonstrate_multiple_environments()
    explain_repair_strategy()
    demonstrate_path_resolution()

    demonstrate_package_detection()
    explain_common_mistakes()
    explain_edge_cases()
    explain_best_practices()
    demonstrate_end_to_end_workflow()
    dependency_management_decision_guide()

    run_internal_tests()

    section("Tutorial execution complete")

    print(
        """
        The demonstrations above cover Python virtual environments, venv,
        pip, requirements files, dependency isolation, dependency resolution,
        reproducibility, troubleshooting, security, and production-oriented
        dependency practices.

        The examples that create environments use temporary directories and
        clean them up after execution.
        """
    )


if __name__ == "__main__":
    main()
