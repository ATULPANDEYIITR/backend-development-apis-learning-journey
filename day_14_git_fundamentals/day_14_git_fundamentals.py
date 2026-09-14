"""
Git Fundamentals: A comprehensive executable study script.

Topic coverage:
- Git terminology and mental model
- repositories and initialization
- working tree, staging area, and commits
- git status, add, commit, log, diff, show
- file tracking and .gitignore
- branches and branch switching
- fast-forward and three-way merges
- merge conflicts and conflict resolution
- rebasing and rebase conflicts
- remote concepts and common workflows
- Git references, HEAD, HEAD~, HEAD^, and detached HEAD
- reset, restore, revert, and their differences
- stash
- tags
- cherry-pick
- reflog and recovery
- commit history design
- Git workflow patterns
- debugging and inspection techniques
- performance and repository hygiene
- security considerations
- practical edge cases and common mistakes

The examples use only Python's standard library and the Git executable.
The script creates temporary repositories, so the demonstrations do not
modify the user's existing repositories.

Requirements:
    Python 3.9+
    Git installed and available on PATH

Run:
    python git_fundamentals.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from textwrap import dedent


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEMO_ROOT: Path | None = None
SECTION_NUMBER = 0


# ---------------------------------------------------------------------------
# Presentation helpers
# ---------------------------------------------------------------------------

def section(title: str) -> None:
    """Print a clearly separated educational section."""
    global SECTION_NUMBER
    SECTION_NUMBER += 1
    print("\n" + "=" * 82)
    print(f"{SECTION_NUMBER}. {title}")
    print("=" * 82)


def subsection(title: str) -> None:
    """Print a subsection title."""
    print(f"\n--- {title} ---")


def explain(text: str) -> None:
    """Print explanatory text without requiring external documentation."""
    print(dedent(text).strip())


def command_preview(command: list[str]) -> str:
    """Return a readable representation of a command."""
    return " ".join(command)


def run(
    command: list[str],
    cwd: Path | None = None,
    *,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    """
    Execute a Git or shell command.

    Git output is captured by default so the script can present it in a
    controlled way. A failed command can optionally be inspected without
    stopping the demonstration.
    """
    print(f"\n$ {command_preview(command)}")

    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=capture,
        check=False,
    )

    if result.stdout:
        print(result.stdout.rstrip())

    if result.stderr:
        print(result.stderr.rstrip())

    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {result.returncode}: "
            f"{command_preview(command)}"
        )

    return result


def git(
    repo: Path,
    *arguments: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a Git command inside a repository."""
    return run(["git", *arguments], cwd=repo, check=check)


def write_file(repo: Path, relative_path: str, content: str) -> Path:
    """Create or replace a text file inside a repository."""
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def append_file(repo: Path, relative_path: str, content: str) -> None:
    """Append text to an existing file."""
    path = repo / relative_path
    with path.open("a", encoding="utf-8") as file:
        file.write(content)


def read_file(repo: Path, relative_path: str) -> str:
    """Read a UTF-8 text file."""
    return (repo / relative_path).read_text(encoding="utf-8")


def initialize_repository(name: str) -> Path:
    """
    Create an isolated Git repository under a temporary directory.

    Git configuration is repository-local so these examples do not depend
    on the user's global Git identity configuration.
    """
    assert DEMO_ROOT is not None
    repo = DEMO_ROOT / name
    repo.mkdir(parents=True, exist_ok=True)

    git(repo, "init", "-b", "main")
    git(repo, "config", "user.name", "Git Fundamentals Student")
    git(repo, "config", "user.email", "student@example.com")
    return repo


def commit(repo: Path, message: str, *paths: str) -> str:
    """Stage selected paths and create a commit, returning its SHA."""
    if paths:
        git(repo, "add", *paths)
    else:
        git(repo, "add", "-A")

    git(repo, "commit", "-m", message)
    result = git(repo, "rev-parse", "HEAD")
    return result.stdout.strip()


def short_sha(repo: Path, revision: str = "HEAD") -> str:
    """Return a short commit identifier."""
    return git(repo, "rev-parse", "--short", revision).stdout.strip()


def print_status(repo: Path) -> None:
    """Show concise repository status."""
    git(repo, "status", "--short", "--branch")


def print_log(repo: Path, count: int = 8) -> None:
    """Display a compact commit graph."""
    git(
        repo,
        "log",
        f"-{count}",
        "--oneline",
        "--decorate",
        "--graph",
        "--all",
    )


# ---------------------------------------------------------------------------
# Environment validation
# ---------------------------------------------------------------------------

def check_git_available() -> None:
    """Verify that Git is installed and executable."""
    section("Environment check")

    result = shutil.which("git")
    if result is None:
        raise RuntimeError(
            "Git was not found on PATH. Install Git and run this script again."
        )

    version = run(["git", "--version"])
    explain(
        """
        Git is available. The demonstrations below use temporary repositories
        rather than the current working directory, which keeps the examples
        isolated from personal projects.
        """
    )


# ---------------------------------------------------------------------------
# Fundamentals
# ---------------------------------------------------------------------------

def demonstrate_git_mental_model() -> None:
    section("Git's mental model")

    explain(
        """
        Git is a distributed version-control system. A repository stores
        objects representing file contents, directory trees, commits, and
        references.

        A normal local workflow has three important areas:

        1. Working tree:
           The files currently visible on disk.

        2. Staging area, also called the index:
           The exact snapshot that will become the next commit.

        3. Repository:
           The committed history stored under .git.

        The distinction between the working tree and staging area is crucial.
        A file can be modified but not staged, staged but then modified again,
        or committed and clean.

        Git does not fundamentally track a sequence of file edits. Commits
        describe snapshots of project state and connect those snapshots into
        a directed acyclic graph.
        """
    )


def demonstrate_repository_initialization() -> None:
    section("Repositories and initialization")

    repo = initialize_repository("fundamentals")

    subsection("Repository structure")
    explain(
        """
        A Git repository is created by git init. The .git directory contains
        Git's internal database and metadata.

        The ordinary project files remain outside .git. Removing .git removes
        the repository metadata while leaving the working files intact.
        """
    )

    run(["git", "status", "--short", "--branch"], cwd=repo)

    subsection("Initial project file")
    write_file(
        repo,
        "README.txt",
        "Git Fundamentals Study Repository\n",
    )
    print_status(repo)


def demonstrate_status_add_commit() -> None:
    section("Working tree, staging area, and commits")

    repo = DEMO_ROOT / "fundamentals"
    assert repo.exists()

    subsection("Untracked files")
    explain(
        """
        An untracked file exists in the working tree but is not yet part of
        the next commit. git status identifies it.
        """
    )
    print_status(repo)

    subsection("Staging")
    git(repo, "add", "README.txt")
    explain(
        """
        git add copies the current version of the selected file into the
        staging area. It does not create a commit.
        """
    )
    print_status(repo)

    subsection("First commit")
    first_commit = git(
        repo,
        "commit",
        "-m",
        "Create initial study file",
    )
    print(first_commit.stdout.rstrip())
    print_status(repo)

    subsection("Modify after staging")
    write_file(
        repo,
        "README.txt",
        "Git Fundamentals Study Repository\n"
        "Working tree modification.\n",
    )

    git(repo, "add", "README.txt")

    append_file(repo, "README.txt", "Second working tree modification.\n")

    explain(
        """
        This is an important Git state:

        The first two lines are staged.
        The third line exists only in the working tree.

        Therefore a commit now would contain the staged snapshot, not every
        current byte visible in the working tree.
        """
    )

    print_status(repo)
    subsection("Inspect staged versus unstaged changes")
    git(repo, "diff", "--cached")
    git(repo, "diff")

    subsection("Commit the complete current state")
    git(repo, "add", "README.txt")
    git(repo, "commit", "-m", "Expand study notes")
    print_status(repo)


def demonstrate_diff_log_show() -> None:
    section("Inspecting history and differences")

    repo = DEMO_ROOT / "fundamentals"

    subsection("git log")
    explain(
        """
        git log displays commit history. Useful formats include:

        --oneline      compact commit identifiers and messages
        --decorate     branch and tag names
        --graph        visualizes relationships
        --all          includes reachable commits from all refs
        """
    )
    print_log(repo)

    subsection("git show")
    git(repo, "show", "--stat", "HEAD")
    git(repo, "show", "--format=fuller", "--no-ext-diff", "HEAD")

    subsection("A new uncommitted change")
    append_file(repo, "README.txt", "A change used to demonstrate diff.\n")
    git(repo, "diff")

    explain(
        """
        git diff compares the working tree against the index.
        git diff --cached compares the index against HEAD.
        git diff HEAD compares the working tree plus index against HEAD.
        """
    )
    git(repo, "diff", "HEAD")

    git(repo, "restore", "README.txt")
    print_status(repo)


# ---------------------------------------------------------------------------
# .gitignore
# ---------------------------------------------------------------------------

def demonstrate_gitignore() -> None:
    section(".gitignore and file selection")

    repo = DEMO_ROOT / "fundamentals"

    write_file(
        repo,
        ".gitignore",
        dedent(
            """
            # Python cache files
            __pycache__/
            *.pyc

            # Local virtual environments
            .venv/
            venv/

            # Environment files containing local configuration or secrets
            .env

            # Operating-system metadata
            .DS_Store
            Thumbs.db

            # Build output
            dist/
            build/
            """
        ).lstrip(),
    )

    write_file(repo, "notes.py", "print('study')\n")
    write_file(repo, "notes.pyc", "not a real bytecode file\n")
    write_file(repo, ".env", "DATABASE_PASSWORD=do-not-commit\n")
    write_file(repo, "dist/output.txt", "generated output\n")

    subsection("Ignored files")
    print_status(repo)

    explain(
        """
        .gitignore affects untracked files. It does not automatically remove
        a file that was already committed.

        If a secret was committed in the past, simply adding the filename to
        .gitignore does not erase the secret from existing history. The secret
        must be revoked or rotated, and history rewriting may be required
        when removal is genuinely necessary.

        Negation patterns beginning with ! can re-include paths that would
        otherwise be ignored.
        """
    )

    git(repo, "check-ignore", "-v", ".env", "dist/output.txt")

    commit(repo, ".gitignore", "notes.py", ".gitignore")

    subsection("Important .gitignore distinction")
    write_file(repo, "tracked.log", "This file will be committed.\n")
    commit(repo, "Add tracked log example", "tracked.log")

    write_file(repo, ".gitignore", ".env\n*.log\n")
    explain(
        """
        tracked.log is already tracked, so the new *.log rule does not make
        it disappear from the repository. Ignore rules primarily control
        whether untracked paths are considered for addition.
        """
    )
    print_status(repo)
    git(repo, "restore", ".gitignore")
    git(repo, "clean", "-fd", check=False)


# ---------------------------------------------------------------------------
# Branches
# ---------------------------------------------------------------------------

def demonstrate_branches() -> None:
    section("Branches and HEAD")

    repo = DEMO_ROOT / "fundamentals"

    explain(
        """
        A branch is essentially a movable reference to a commit. HEAD
        identifies the commit or branch currently checked out.

        Creating a branch does not duplicate the repository's files. It
        creates another reference that can move independently as commits are
        created.
        """
    )

    git(repo, "switch", "-c", "feature/profile")
    write_file(
        repo,
        "profile.txt",
        "Profile feature developed on a branch.\n",
    )
    commit(repo, "Add profile feature", "profile.txt")

    subsection("Branch listing")
    git(repo, "branch", "--verbose")

    subsection("Return to main")
    git(repo, "switch", "main")
    print_status(repo)

    explain(
        """
        The feature file is not visible on main because main points to a
        different commit whose snapshot does not contain that file.
        """
    )

    print_log(repo)


def demonstrate_fast_forward_merge() -> None:
    section("Fast-forward merge")

    repo = initialize_repository("fast_forward")
    write_file(repo, "app.txt", "version 1\n")
    commit(repo, "Create application")

    git(repo, "switch", "-c", "feature")
    append_file(repo, "app.txt", "feature line\n")
    commit(repo, "Add feature")

    git(repo, "switch", "main")

    subsection("Before merge")
    print_log(repo)

    explain(
        """
        main has not developed independently. The feature branch contains
        main's previous commit plus newer commits.

        A fast-forward merge can simply move main's branch reference forward
        to the feature commit. No merge commit is required.
        """
    )

    git(repo, "merge", "feature")
    print_log(repo)


def demonstrate_three_way_merge() -> None:
    section("Three-way merge")

    repo = initialize_repository("three_way_merge")
    write_file(repo, "story.txt", "Beginning\n")
    commit(repo, "Create story")

    git(repo, "switch", "-c", "feature")
    append_file(repo, "story.txt", "Feature chapter\n")
    commit(repo, "Add feature chapter")

    git(repo, "switch", "main")
    append_file(repo, "story.txt", "Main chapter\n")
    commit(repo, "Add main chapter")

    subsection("Diverged history")
    print_log(repo)

    explain(
        """
        Both branches now contain changes that descend from the same earlier
        commit. Git cannot move main directly to feature because main has its
        own commit.

        A three-way merge compares:

        1. The common ancestor.
        2. The current branch tip.
        3. The branch being merged.

        If the changes are compatible, Git combines them and creates a merge
        commit when needed.
        """
    )

    git(repo, "merge", "--no-edit", "feature")
    print_log(repo)
    print(read_file(repo, "story.txt"))


# ---------------------------------------------------------------------------
# Merge conflicts
# ---------------------------------------------------------------------------

def demonstrate_merge_conflict() -> None:
    section("Merge conflicts and conflict resolution")

    repo = initialize_repository("merge_conflict")
    write_file(repo, "config.txt", "mode=standard\n")
    commit(repo, "Create configuration")

    git(repo, "switch", "-c", "feature")
    write_file(repo, "config.txt", "mode=fast\n")
    commit(repo, "Use fast mode")

    git(repo, "switch", "main")
    write_file(repo, "config.txt", "mode=safe\n")
    commit(repo, "Use safe mode")

    subsection("Attempt conflicting merge")
    result = git(repo, "merge", "feature", check=False)

    if result.returncode == 0:
        raise RuntimeError("The demonstration expected a merge conflict.")

    print_status(repo)

    explain(
        """
        A conflict means Git could not automatically combine the changes.

        Conflict markers commonly look like:

        <<<<<<< HEAD
        current branch content
        =======
        incoming branch content
        >>>>>>> feature

        The correct resolution is a deliberate human decision. Remove the
        markers, create the desired final content, stage the resolved file,
        and complete the merge.

        Git records the conflict state in the index until it is resolved.
        """
    )

    write_file(repo, "config.txt", "mode=fast-and-safe\n")
    git(repo, "add", "config.txt")
    git(repo, "commit", "-m", "Merge feature with resolved configuration")

    subsection("Resolved history")
    print_log(repo)
    print(read_file(repo, "config.txt"))


# ---------------------------------------------------------------------------
# Rebase
# ---------------------------------------------------------------------------

def demonstrate_rebase() -> None:
    section("Rebase")

    repo = initialize_repository("rebase")
    write_file(repo, "app.txt", "base\n")
    commit(repo, "Base commit")

    git(repo, "switch", "-c", "feature")
    append_file(repo, "app.txt", "feature\n")
    commit(repo, "Feature work")

    git(repo, "switch", "main")
    append_file(repo, "app.txt", "main\n")
    commit(repo, "Main work")

    subsection("History before rebase")
    print_log(repo)

    git(repo, "switch", "feature")

    explain(
        """
        Rebase changes the base of a sequence of commits.

        Conceptually, Git takes the feature commits that are not present on
        main, temporarily replays them, and creates new commit objects based
        on the newer main tip.

        This means rebased commits receive new identities. Rebase is therefore
        history rewriting, not merely a cosmetic history operation.
        """
    )

    git(repo, "rebase", "main")

    subsection("History after rebase")
    print_log(repo)

    explain(
        """
        The resulting feature history is linear:

        main base -> main work -> feature work

        Rebase can make private or local history easier to read. It must be
        used carefully on commits that other people already depend on because
        rewritten commit IDs can create duplicated or conflicting history.
        """
    )


def demonstrate_rebase_conflict() -> None:
    section("Rebase conflicts")

    repo = initialize_repository("rebase_conflict")
    write_file(repo, "settings.txt", "theme=default\n")
    commit(repo, "Create settings")

    git(repo, "switch", "-c", "feature")
    write_file(repo, "settings.txt", "theme=dark\n")
    commit(repo, "Choose dark theme")

    git(repo, "switch", "main")
    write_file(repo, "settings.txt", "theme=light\n")
    commit(repo, "Choose light theme")

    git(repo, "switch", "feature")

    result = git(repo, "rebase", "main", check=False)

    if result.returncode == 0:
        raise RuntimeError("The demonstration expected a rebase conflict.")

    print_status(repo)

    explain(
        """
        During a rebase conflict, the usual sequence is:

        1. Inspect the conflict.
        2. Edit the conflicted files.
        3. Stage the resolution with git add.
        4. Run git rebase --continue.

        If the rebase should not proceed, git rebase --abort returns the
        branch to the state it had before the rebase started.

        The demonstration resolves the conflict by choosing a combined value.
        """
    )

    write_file(repo, "settings.txt", "theme=adaptive\n")
    git(repo, "add", "settings.txt")

    # GIT_EDITOR=true avoids opening an interactive editor in an automated run.
    result = subprocess.run(
        ["git", "rebase", "--continue"],
        cwd=str(repo),
        text=True,
        capture_output=True,
        env={**os.environ, "GIT_EDITOR": "true"},
        check=False,
    )

    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip())

    if result.returncode != 0:
        raise RuntimeError("Rebase continuation failed.")

    print_log(repo)


# ---------------------------------------------------------------------------
# Reset, restore, revert
# ---------------------------------------------------------------------------

def demonstrate_reset_restore_revert() -> None:
    section("reset, restore, and revert")

    repo = initialize_repository("undo_commands")
    write_file(repo, "file.txt", "one\n")
    commit(repo, "Add one")

    write_file(repo, "file.txt", "one\ntwo\n")
    commit(repo, "Add two")

    write_file(repo, "file.txt", "one\ntwo\nthree\n")

    subsection("git restore")
    explain(
        """
        git restore operates primarily on file content.

        git restore file.txt
        restores the working tree version from the index.

        git restore --staged file.txt
        removes a file's staged changes from the index while leaving the
        working-tree modification intact.
        """
    )
    print_status(repo)
    git(repo, "restore", "file.txt")
    print_status(repo)

    subsection("git reset")
    write_file(repo, "file.txt", "one\ntwo\nthree\n")
    git(repo, "add", "file.txt")

    explain(
        """
        git reset can move the current branch reference and can also modify
        the index depending on the mode.

        --soft:
            Move HEAD, keep index and working tree.

        --mixed:
            Move HEAD, reset index, keep working tree. This is the default.

        --hard:
            Move HEAD, reset index and working tree. Uncommitted changes can
            be destroyed, so it requires deliberate use.
        """
    )

    git(repo, "reset", "HEAD", "--", "file.txt")
    print_status(repo)

    subsection("git revert")
    write_file(repo, "file.txt", "one\ntwo\nthree\n")
    commit(repo, "Add three")

    explain(
        """
        git revert creates a new commit that reverses the effect of an
        earlier commit. It is usually safer than rewriting shared history
        because the original commit remains part of the history.
        """
    )

    target = short_sha(repo)
    git(repo, "revert", "--no-edit", target)

    print_log(repo)
    print("Current file content:")
    print(read_file(repo, "file.txt"))


# ---------------------------------------------------------------------------
# HEAD and references
# ---------------------------------------------------------------------------

def demonstrate_references_and_head() -> None:
    section("HEAD, commit references, and detached HEAD")

    repo = initialize_repository("references")
    write_file(repo, "history.txt", "A\n")
    commit(repo, "Commit A")

    write_file(repo, "history.txt", "A\nB\n")
    commit(repo, "Commit B")

    write_file(repo, "history.txt", "A\nB\nC\n")
    commit(repo, "Commit C")

    subsection("Common revision expressions")
    expressions = [
        "HEAD",
        "HEAD~1",
        "HEAD~2",
        "HEAD^",
    ]

    for expression in expressions:
        result = git(repo, "rev-parse", "--short", expression)
        print(f"{expression:8} -> {result.stdout.strip()}")

    explain(
        """
        HEAD means the currently checked-out position.

        HEAD~1 means the first-parent ancestor one generation behind HEAD.
        HEAD~2 moves two generations through the first-parent chain.
        HEAD^ means the first parent of a commit.

        For ordinary linear history, HEAD~1 and HEAD^ commonly refer to the
        same commit. Merge commits can have multiple parents, making parent
        notation more significant.
        """
    )

    subsection("Detached HEAD")
    old_commit = git(repo, "rev-parse", "HEAD~1").stdout.strip()
    git(repo, "switch", "--detach", old_commit)
    print_status(repo)

    explain(
        """
        Detached HEAD means HEAD points directly to a commit instead of a
        branch reference.

        It is useful for inspecting or testing historical states. If commits
        are created here and no branch or tag retains them, they can eventually
        become unreachable and eligible for cleanup.

        A branch can preserve such work:

            git switch -c experiment
        """
    )

    git(repo, "switch", "main")


# ---------------------------------------------------------------------------
# Stash
# ---------------------------------------------------------------------------

def demonstrate_stash() -> None:
    section("Stash")

    repo = initialize_repository("stash")
    write_file(repo, "app.txt", "stable\n")
    commit(repo, "Stable application")

    write_file(repo, "app.txt", "stable\nwork in progress\n")
    write_file(repo, "temporary.txt", "temporary work\n")

    subsection("Save work temporarily")
    print_status(repo)
    git(repo, "stash", "push", "-u", "-m", "Work in progress")

    print_status(repo)
    git(repo, "stash", "list")

    explain(
        """
        git stash stores local modifications in stash commits and restores a
        clean working tree.

        The -u option includes untracked files. Without it, ordinary untracked
        files are not normally included.

        Stash is useful when changing context temporarily, but it should not
        become a permanent substitute for meaningful commits.
        """
    )

    subsection("Restore the work")
    git(repo, "stash", "pop")
    print_status(repo)
    print(read_file(repo, "app.txt"))


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

def demonstrate_tags() -> None:
    section("Tags")

    repo = initialize_repository("tags")
    write_file(repo, "release.txt", "Release 1.0\n")
    commit(repo, "Prepare release 1.0")

    explain(
        """
        Tags are references intended to identify important points in history,
        such as releases.

        Lightweight tags are simple references.
        Annotated tags are Git objects containing metadata such as the tagger,
        date, message, and target object.

        Annotated tags are commonly preferable for formal releases.
        """
    )

    git(repo, "tag", "v1.0.0")
    git(
        repo,
        "tag",
        "-a",
        "v1.1.0",
        "-m",
        "Release 1.1.0",
    )

    git(repo, "tag", "--list")
    git(repo, "show", "--stat", "v1.1.0")


# ---------------------------------------------------------------------------
# Cherry-pick
# ---------------------------------------------------------------------------

def demonstrate_cherry_pick() -> None:
    section("Cherry-pick")

    repo = initialize_repository("cherry_pick")
    write_file(repo, "app.txt", "base\n")
    commit(repo, "Base application")

    git(repo, "switch", "-c", "feature")
    write_file(repo, "feature.txt", "Important isolated fix\n")
    feature_commit = commit(repo, "Add isolated fix", "feature.txt")

    git(repo, "switch", "main")

    explain(
        """
        cherry-pick applies the change introduced by an existing commit onto
        the current branch.

        It creates a new commit. The new commit has a different identity even
        though it represents a similar change.

        Cherry-pick is useful for selectively transferring a bug fix or small
        change without merging an entire branch.
        """
    )

    git(repo, "cherry-pick", feature_commit)
    print_log(repo)


# ---------------------------------------------------------------------------
# Remotes and collaboration
# ---------------------------------------------------------------------------

def demonstrate_remote_concepts() -> None:
    section("Remote repositories and collaboration")

    explain(
        """
        A remote is a named reference to another repository, often hosted on
        a server.

        Common terminology:

        origin:
            Conventional default name for the primary remote.

        fetch:
            Download remote objects and update remote-tracking references.

        pull:
            Fetch and then integrate changes, commonly by merge or rebase
            depending on configuration and command options.

        push:
            Send local commits and related objects to a remote and update a
            remote branch when permitted.

        origin/main:
            A remote-tracking reference representing the last fetched state of
            the remote's main branch.

        Remote-tracking references are not the same thing as local branches.
        """
    )

    repo = initialize_repository("remote")
    write_file(repo, "README.txt", "Remote demonstration\n")
    commit(repo, "Initial remote demonstration")

    remote_repo = DEMO_ROOT / "remote_server.git"
    git(
        DEMO_ROOT,
        "init",
        "--bare",
        str(remote_repo),
    )

    git(repo, "remote", "add", "origin", str(remote_repo))
    git(repo, "push", "-u", "origin", "main")

    subsection("Remote information")
    git(repo, "remote", "-v")
    git(repo, "branch", "-vv")

    explain(
        """
        A bare repository is commonly used as a server-side repository
        because it does not have a working tree. The local demonstration uses
        a bare repository to show the mechanics without requiring internet
        access or a hosted Git service.
        """
    )


def demonstrate_fetch_and_divergence() -> None:
    section("Fetch, pull, push, and divergence")

    source = initialize_repository("collaboration_source")
    write_file(source, "app.txt", "initial\n")
    commit(source, "Initial application")

    remote = DEMO_ROOT / "collaboration_remote.git"
    git(DEMO_ROOT, "init", "--bare", str(remote))

    git(source, "remote", "add", "origin", str(remote))
    git(source, "push", "-u", "origin", "main")

    clone_a = DEMO_ROOT / "developer_a"
    clone_b = DEMO_ROOT / "developer_b"

    git(
        DEMO_ROOT,
        "clone",
        str(remote),
        str(clone_a),
    )
    git(
        DEMO_ROOT,
        "clone",
        str(remote),
        str(clone_b),
    )

    for clone in (clone_a, clone_b):
        git(clone, "config", "user.name", clone.name)
        git(clone, "config", "user.email", f"{clone.name}@example.com")

    subsection("Developer A pushes")
    append_file(clone_a, "app.txt", "developer A\n")
    commit(clone_a, "Developer A change")
    git(clone_a, "push")

    subsection("Developer B fetches")
    git(clone_b, "fetch", "origin")
    git(clone_b, "log", "--oneline", "--decorate", "origin/main", "-3")

    explain(
        """
        fetch downloads remote history but does not change the current local
        branch's working tree.

        pull performs a fetch followed by an integration step. Depending on
        configuration and flags, that integration can use merge or rebase.

        If two developers create different commits from the same old point,
        the branches diverge. A later pull or merge may need to integrate
        those histories.
        """
    )

    append_file(clone_b, "app.txt", "developer B\n")
    commit(clone_b, "Developer B change")

    result = git(clone_b, "push", check=False)
    if result.returncode == 0:
        raise RuntimeError("Expected the push to be rejected after divergence.")

    explain(
        """
        The push is rejected because the remote contains commits that the
        local branch does not contain. This is a non-fast-forward situation.

        A safe workflow is to fetch, inspect the divergence, integrate the
        remote work through merge or rebase, resolve conflicts if necessary,
        test the result, and then push.
        """
    )

    git(clone_b, "pull", "--no-rebase", "origin", "main", check=False)

    # Resolve the predictable append-only conflict if one occurs.
    content = read_file(clone_b, "app.txt")
    if "<<<<<<<" in content:
        write_file(
            clone_b,
            "app.txt",
            "initial\n"
            "developer A\n"
            "developer B\n",
        )
        git(clone_b, "add", "app.txt")
        git(
            clone_b,
            "commit",
            "-m",
            "Merge remote changes",
        )

    git(clone_b, "push")
    print_log(clone_b)


# ---------------------------------------------------------------------------
# Merge versus rebase
# ---------------------------------------------------------------------------

def demonstrate_merge_vs_rebase() -> None:
    section("Merge versus rebase")

    explain(
        """
        Merge:
            Preserves the existing branch topology and may create a merge
            commit. It is appropriate when preserving the fact that two lines
            of development were integrated is useful.

        Rebase:
            Replays commits onto another base and creates new commit objects.
            It produces a more linear history but rewrites commit identities.

        Important practical rule:

            Do not casually rebase commits that have already been shared and
            that other people have based work upon.

        A merge records integration without rewriting existing commits.
        A rebase changes the ancestry of the replayed commits.

        Neither command is universally superior. The correct choice depends
        on collaboration policy, history requirements, and whether the
        affected commits are private or already shared.
        """
    )

    print(
        "\nDecision examples:"
        "\n  Private feature branch before publication -> rebase can be useful."
        "\n  Shared public branch -> avoid history rewriting."
        "\n  Preserving branch topology matters -> merge."
        "\n  Small selective fix -> cherry-pick may be appropriate."
    )


# ---------------------------------------------------------------------------
# Reflog and recovery
# ---------------------------------------------------------------------------

def demonstrate_reflog_recovery() -> None:
    section("Reflog and recovery")

    repo = initialize_repository("recovery")
    write_file(repo, "important.txt", "important data\n")
    first = commit(repo, "Important commit")

    write_file(repo, "important.txt", "important data\nmore data\n")
    second = commit(repo, "Second important commit")

    subsection("Reflog")
    git(repo, "reflog", "--oneline", "-8")

    explain(
        """
        The reflog records movements of local references such as HEAD.

        It can help recover commits after accidental operations such as a
        reset or branch movement, provided the relevant reflog entry still
        exists.

        A typical recovery pattern is:

            1. Inspect git reflog.
            2. Identify the desired historical commit.
            3. Create a recovery branch pointing to that commit.

        Example:
            git switch -c recovery <commit>

        Reflogs are local mechanisms and should not be treated as a remote
        backup system.
        """
    )

    git(repo, "reset", "--hard", first)
    print_log(repo)

    git(repo, "switch", "-c", "recovered", second)
    print_log(repo)


# ---------------------------------------------------------------------------
# Commit design
# ---------------------------------------------------------------------------

def demonstrate_commit_design() -> None:
    section("Commit design and atomic changes")

    repo = initialize_repository("commit_design")

    write_file(repo, "calculator.py", "def add(a, b):\n    return a + b\n")
    write_file(repo, "README.txt", "Calculator\n")
    commit(repo, "Create calculator baseline")

    append_file(
        repo,
        "calculator.py",
        "\ndef subtract(a, b):\n    return a - b\n",
    )
    append_file(
        repo,
        "README.txt",
        "\nUsage information.\n",
    )

    explain(
        """
        A commit should ideally represent a coherent, reviewable unit of
        change.

        Benefits of focused commits include:

        - easier code review
        - easier debugging
        - clearer history
        - safer reverts
        - simpler cherry-picks
        - easier identification of regressions

        Staging lets a developer separate unrelated changes into different
        commits.
        """
    )

    git(repo, "add", "calculator.py")
    git(repo, "commit", "-m", "Add subtraction operation")

    git(repo, "add", "README.txt")
    git(repo, "commit", "-m", "Document calculator usage")

    print_log(repo)


# ---------------------------------------------------------------------------
# File paths, rename, delete
# ---------------------------------------------------------------------------

def demonstrate_file_operations() -> None:
    section("Tracking creation, modification, rename, and deletion")

    repo = initialize_repository("file_operations")

    write_file(repo, "old_name.txt", "tracked content\n")
    commit(repo, "Add original file")

    git(repo, "mv", "old_name.txt", "new_name.txt")
    git(repo, "commit", "-m", "Rename tracked file")

    git(repo, "rm", "new_name.txt")
    git(repo, "commit", "-m", "Remove obsolete file")

    print_log(repo)

    explain(
        """
        Git detects renames through similarity between snapshots. A rename is
        represented internally as changes to tree entries and file contents;
        rename detection is an interpretation used by commands and tools.

        git mv and git rm provide convenient workflows, but equivalent changes
        can also be staged using ordinary filesystem operations followed by
        git add and git rm.
        """
    )


# ---------------------------------------------------------------------------
# Branch deletion and safety
# ---------------------------------------------------------------------------

def demonstrate_branch_lifecycle() -> None:
    section("Branch lifecycle and safe deletion")

    repo = initialize_repository("branch_lifecycle")
    write_file(repo, "app.txt", "base\n")
    commit(repo, "Base")

    git(repo, "switch", "-c", "finished-feature")
    append_file(repo, "app.txt", "feature complete\n")
    commit(repo, "Complete feature")

    git(repo, "switch", "main")
    git(repo, "merge", "--ff-only", "finished-feature")

    subsection("Delete merged branch")
    git(repo, "branch", "-d", "finished-feature")
    git(repo, "branch", "--list")

    explain(
        """
        git branch -d performs a safety-oriented deletion of a branch that
        Git considers merged.

        git branch -D forces deletion and can remove a branch reference even
        when its commits are not merged. Forced deletion should be deliberate
        because it can make unique work harder to locate.
        """
    )


# ---------------------------------------------------------------------------
# Common mistakes
# ---------------------------------------------------------------------------

def demonstrate_common_mistakes() -> None:
    section("Common mistakes and their mechanics")

    repo = initialize_repository("mistakes")
    write_file(repo, "app.txt", "one\n")
    commit(repo, "Initial state")

    subsection("Mistake: editing but forgetting git add")
    append_file(repo, "app.txt", "two\n")
    git(repo, "commit", "-m", "Attempt commit without staging", check=False)
    print_status(repo)

    explain(
        """
        A normal git commit uses the index. If a modified file has not been
        staged, its newest changes are not included in the commit.

        Correct pattern:
            git add app.txt
            git commit -m "Describe the change"
        """
    )

    git(repo, "add", "app.txt")
    git(repo, "commit", "-m", "Stage and commit change")

    subsection("Mistake: working on the wrong branch")
    git(repo, "switch", "-c", "feature")
    write_file(repo, "feature.txt", "feature work\n")

    explain(
        """
        Before making substantial changes, inspect:

            git status
            git branch --show-current

        A branch name is not merely a label. It determines where new commits
        are attached.
        """
    )

    git(repo, "restore", "feature.txt")
    git(repo, "switch", "main")

    subsection("Mistake: assuming .gitignore removes tracked secrets")
    write_file(repo, "secret.txt", "example-secret\n")
    commit(repo, "Accidentally track secret example", "secret.txt")

    write_file(repo, ".gitignore", "secret.txt\n")
    print_status(repo)

    explain(
        """
        The tracked secret remains tracked. Ignoring it does not remove its
        previous content from history.

        Real credentials must be revoked or rotated immediately. Repository
        history cleanup is a separate operation and cannot undo exposure
        that has already occurred.
        """
    )

    git(repo, "rm", "--cached", "secret.txt")
    git(repo, "commit", "-m", "Stop tracking secret example")
    print_status(repo)


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

def demonstrate_security() -> None:
    section("Git security considerations")

    explain(
        """
        Git repositories often contain source code, configuration, build
        files, deployment definitions, and history. Security failures can
        therefore occur through version control itself.

        Important rules:

        1. Do not commit passwords, private keys, API tokens, database
           credentials, or personal access tokens.

        2. Use .gitignore for local configuration files, but understand that
           .gitignore is not a secret-management system.

        3. If a secret is committed, rotate or revoke it. Removing the file
           from the current snapshot does not make the old secret safe.

        4. Review diffs before committing:
               git diff
               git diff --cached

        5. Protect important branches through repository-hosting policies,
           required reviews, status checks, and restricted force pushes.

        6. Treat downloaded repositories and hooks as potentially executable
           code. Review unfamiliar repository behavior before running scripts.

        7. Be careful with Git hooks. Hooks can execute commands automatically
           during operations such as commits and merges.

        8. Verify remotes before pushing:
               git remote -v

        9. Do not assume a private repository means a secret is safe forever.
           Access controls, backups, logs, forks, caches, and historical
           objects can all affect exposure.
        """
    )

    repo = initialize_repository("security")
    write_file(repo, ".gitignore", ".env\n*.key\n")
    write_file(repo, ".env", "DATABASE_PASSWORD=example-only\n")
    write_file(repo, "private.key", "example-key-material\n")

    print_status(repo)
    git(repo, "check-ignore", "-v", ".env", "private.key")


# ---------------------------------------------------------------------------
# Performance and repository hygiene
# ---------------------------------------------------------------------------

def demonstrate_performance_and_hygiene() -> None:
    section("Performance and repository hygiene")

    explain(
        """
        Git is efficient because it stores content as objects and uses
        compression and indexing mechanisms. Good repository structure still
        matters.

        Practical considerations:

        - Avoid committing generated build output when it can be reproduced.
        - Avoid large binary artifacts in ordinary source history.
        - Use appropriate artifact storage when large files are genuinely
          required.
        - Keep ignore rules precise.
        - Keep commits focused.
        - Avoid repeatedly rewriting huge histories without a reason.
        - Use shallow or partial clone strategies when repository size and
          network cost justify them.
        - Run repository maintenance commands when appropriate for large or
          heavily used repositories.

        Useful inspection commands include:

            git count-objects -v
            git gc
            git fsck

        Repository maintenance should be understood before running commands
        that prune unreachable objects, especially when recovering work.
        """
    )

    repo = initialize_repository("performance")
    for index in range(20):
        write_file(
            repo,
            f"data/file_{index:02d}.txt",
            f"Generated example file {index}\n",
        )

    commit(repo, "Create sample dataset")
    git(repo, "count-objects", "-v")


# ---------------------------------------------------------------------------
# Advanced history inspection
# ---------------------------------------------------------------------------

def demonstrate_advanced_inspection() -> None:
    section("Advanced history inspection")

    repo = initialize_repository("inspection")
    write_file(repo, "app.py", "print('v1')\n")
    commit(repo, "Version one")

    write_file(repo, "app.py", "print('v2')\n")
    commit(repo, "Version two")

    write_file(repo, "app.py", "print('v3')\n")
    commit(repo, "Version three")

    subsection("Branch and commit identity")
    git(repo, "branch", "--show-current")
    git(repo, "rev-parse", "HEAD")
    git(repo, "rev-parse", "--show-toplevel")

    subsection("Inspect object type")
    sha = git(repo, "rev-parse", "HEAD").stdout.strip()
    git(repo, "cat-file", "-t", sha)

    subsection("Blame")
    git(repo, "blame", "app.py")

    subsection("Search commit messages")
    git(repo, "log", "--oneline", "--grep=two", "--all")

    explain(
        """
        Useful advanced inspection commands include:

        git rev-parse
            Resolve references and repository paths.

        git cat-file
            Inspect Git objects at a low level.

        git blame
            Associate lines with commits and authors. It is best used to
            understand historical context, not to assign personal blame.

        git log --grep
            Search commit messages.

        git log -S
            Find commits where the number of occurrences of a string changed.

        git log -G
            Search for changes matching a regular expression.

        These tools are valuable when investigating when and why a behavior
        changed.
        """
    )

    git(repo, "log", "--oneline", "-S", "v2", "--", "app.py")
    git(repo, "log", "--oneline", "-G", "print", "--", "app.py")


# ---------------------------------------------------------------------------
# Bisect
# ---------------------------------------------------------------------------

def demonstrate_bisect() -> None:
    section("git bisect for regression debugging")

    repo = initialize_repository("bisect")

    versions = [
        ("v1", False),
        ("v2", False),
        ("v3", False),
        ("v4", True),
        ("v5", True),
        ("v6", True),
    ]

    for version, broken in versions:
        write_file(
            repo,
            "program.txt",
            f"version={version}\nbroken={str(broken).lower()}\n",
        )
        commit(repo, f"Create {version}")

    explain(
        """
        git bisect performs a binary search through commit history.

        The developer identifies one known-good commit and one known-bad
        commit. Git checks out a midpoint. The developer tests that revision
        and tells Git whether it is good or bad. Git then narrows the search.

        This can reduce the number of tests needed to find a regression from
        linear growth to approximately logarithmic growth.

        The example uses a deterministic file instead of a real test suite.
        """
    )

    good = git(repo, "rev-parse", "HEAD~5").stdout.strip()
    bad = git(repo, "rev-parse", "HEAD").stdout.strip()

    git(repo, "bisect", "start")
    git(repo, "bisect", "bad", bad)
    git(repo, "bisect", "good", good)

    # The bisect result can be identified automatically from the test file.
    while True:
        status = git(repo, "bisect", "status")
        current = read_file(repo, "program.txt")

        if "broken=true" in current:
            result = "bad"
        else:
            result = "good"

        response = git(repo, "bisect", result, check=False)

        combined = (response.stdout or "") + (response.stderr or "")
        print(combined.rstrip())

        if "is the first bad commit" in combined:
            break

    git(repo, "bisect", "reset")
    print_log(repo)


# ---------------------------------------------------------------------------
# Workflow comparison
# ---------------------------------------------------------------------------

def demonstrate_workflows() -> None:
    section("Practical Git workflows")

    explain(
        """
        A simple individual workflow:

            1. git status
            2. git switch -c feature/name
            3. edit files
            4. git diff
            5. git add <files>
            6. git diff --cached
            7. git commit -m "Focused change"
            8. git fetch origin
            9. integrate current main when appropriate
           10. git push -u origin feature/name

        A common pull-request workflow:

            main
              |
              +---- feature branch
                        |
                        +---- focused commits
                        |
                        +---- review
                        |
                        +---- merge or squash merge

        A trunk-oriented workflow:

            Developers integrate small changes frequently into a shared
            mainline, often protected by automated tests and review rules.

        Git provides mechanics. The exact workflow is a team policy decision.
        The important principles are explicit history, reviewable changes,
        reliable tests, and controlled integration.
        """
    )

    comparison = [
        ("merge", "Preserves topology", "Shared history and explicit integration"),
        ("rebase", "Linearizes by replaying", "Private or controlled feature history"),
        ("cherry-pick", "Copies one change as a new commit", "Selective fixes"),
        ("revert", "Adds an inverse commit", "Undoing shared history safely"),
        ("reset", "Moves a reference and optionally index/worktree", "Local history correction"),
        ("restore", "Restores file content", "Discarding or unstaging file changes"),
    ]

    print("\nCommand comparison:")
    print(f"{'Command':<14} {'Primary effect':<40} Typical use")
    print("-" * 90)
    for command, effect, use in comparison:
        print(f"{command:<14} {effect:<40} {use}")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def demonstrate_edge_cases() -> None:
    section("Important edge cases")

    repo = initialize_repository("edge_cases")

    subsection("Empty directories")
    explain(
        """
        Git tracks files, not empty directories. Creating an empty directory
        alone does not produce a Git object representing that directory.

        A project that needs an otherwise-empty directory often places a
        deliberate placeholder file inside it, though the placeholder is a
        project convention rather than a Git requirement.
        """
    )

    (repo / "empty_directory").mkdir()
    print_status(repo)

    subsection("Filename case sensitivity")
    explain(
        """
        Case sensitivity depends partly on the operating system and filesystem.
        A repository may contain names that behave differently on a
        case-sensitive filesystem than on a case-insensitive one.

        Cross-platform projects should avoid relying on ambiguous case-only
        filename differences.
        """
    )

    subsection("Line endings")
    explain(
        """
        Windows commonly uses CRLF line endings, while Unix-like systems
        commonly use LF. Git can normalize line endings through attributes and
        configuration.

        For cross-platform projects, an explicit .gitattributes policy is
        often clearer than relying entirely on local defaults.
        """
    )

    write_file(
        repo,
        ".gitattributes",
        "* text=auto\n"
        "*.sh text eol=lf\n"
        "*.bat text eol=crlf\n",
    )
    git(repo, "add", ".gitattributes")
    git(repo, "commit", "-m", "Define line-ending policy")

    subsection("Binary files")
    write_file(repo, "binary-description.txt", "Binary files are opaque to normal text diffing.\n")
    commit(repo, "Document binary consideration")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def demonstrate_configuration() -> None:
    section("Git configuration")

    repo = initialize_repository("configuration")

    explain(
        """
        Git configuration has multiple scopes:

        system:
            Applies broadly to the installation.

        global:
            Applies to the user account.

        local:
            Applies only to the current repository.

        Workflows should avoid accidentally changing global configuration
        when only a repository-specific setting is intended.

        Common settings include user identity, default branch naming, editor
        behavior, aliases, diff tools, merge behavior, and pull strategy.
        """
    )

    git(repo, "config", "--local", "user.name")
    git(repo, "config", "--local", "user.email")

    git(repo, "config", "--local", "core.autocrlf", "false")
    git(repo, "config", "--local", "--list")


# ---------------------------------------------------------------------------
# Git object model
# ---------------------------------------------------------------------------

def demonstrate_object_model() -> None:
    section("Git's object model")

    repo = initialize_repository("object_model")
    write_file(repo, "a.txt", "alpha\n")
    commit(repo, "Create alpha")

    sha = git(repo, "rev-parse", "HEAD").stdout.strip()

    explain(
        """
        Git's core object model includes:

        Blob:
            Stores file content.

        Tree:
            Represents a directory snapshot and maps names to blobs or other
            trees.

        Commit:
            Points to a tree and records metadata and parent commit(s).

        Tag object:
            Can annotate another Git object with metadata.

        References such as branches and tags point to objects. HEAD identifies
        the current checkout position.

        This model explains why Git can branch cheaply. Creating a branch
        normally creates or updates a small reference rather than copying an
        entire working directory.
        """
    )

    print(f"HEAD commit object: {sha}")
    git(repo, "cat-file", "-p", sha)

    tree = git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
    print(f"\nTree object: {tree}")
    git(repo, "cat-file", "-p", tree)

    blob = git(repo, "rev-parse", "HEAD:a.txt").stdout.strip()
    print(f"\nBlob object: {blob}")
    git(repo, "cat-file", "-t", blob)
    git(repo, "cat-file", "-p", blob)


# ---------------------------------------------------------------------------
# Best-practice checklist
# ---------------------------------------------------------------------------

def print_best_practices() -> None:
    section("Git best-practice checklist")

    practices = [
        "Check git status before important operations.",
        "Review git diff before staging.",
        "Review git diff --cached before committing.",
        "Use focused commits with meaningful messages.",
        "Keep generated artifacts out of source history when appropriate.",
        "Use .gitignore for local and generated files.",
        "Never treat .gitignore as a secret-management system.",
        "Create branches for isolated work when the workflow calls for them.",
        "Fetch before making decisions about remote divergence.",
        "Do not force-push shared history without an explicit team policy.",
        "Prefer revert over rewriting already-shared history.",
        "Use rebase carefully because it creates new commit identities.",
        "Resolve conflicts by understanding both sides rather than blindly choosing one.",
        "Run tests after merges, rebases, cherry-picks, and conflict resolutions.",
        "Use tags to identify significant releases.",
        "Use reflog when recovering from accidental local reference movement.",
        "Verify remotes before pushing sensitive or important work.",
        "Keep credentials and private keys outside the repository.",
        "Protect important branches with appropriate repository policies.",
        "Treat unfamiliar hooks and repository scripts as executable code.",
    ]

    for index, practice in enumerate(practices, start=1):
        print(f"{index:02d}. {practice}")


# ---------------------------------------------------------------------------
# Final reference
# ---------------------------------------------------------------------------

def print_command_reference() -> None:
    section("Compact command reference")

    commands = {
        "Initialize": [
            "git init",
            "git clone <url>",
        ],
        "Inspect": [
            "git status",
            "git log --oneline --graph --decorate --all",
            "git diff",
            "git diff --cached",
            "git show <commit>",
        ],
        "Stage and commit": [
            "git add <path>",
            "git add -A",
            'git commit -m "message"',
        ],
        "Branches": [
            "git branch",
            "git switch -c <branch>",
            "git switch <branch>",
            "git branch -d <branch>",
        ],
        "Integration": [
            "git merge <branch>",
            "git rebase <branch>",
            "git cherry-pick <commit>",
        ],
        "Undo": [
            "git restore <path>",
            "git restore --staged <path>",
            "git reset --soft <commit>",
            "git reset <commit>",
            "git reset --hard <commit>",
            "git revert <commit>",
        ],
        "Remote": [
            "git remote -v",
            "git fetch origin",
            "git pull",
            "git push",
            "git push -u origin <branch>",
        ],
        "Temporary and recovery": [
            "git stash push -u -m <message>",
            "git stash list",
            "git stash pop",
            "git reflog",
            "git switch -c <recovery-branch> <commit>",
        ],
        "Release and debugging": [
            "git tag",
            "git tag -a <tag> -m <message>",
            "git blame <file>",
            "git log -S <text> -- <file>",
            "git log -G <regex> -- <file>",
            "git bisect start",
        ],
    }

    for category, entries in commands.items():
        print(f"\n{category}:")
        for entry in entries:
            print(f"  {entry}")


# ---------------------------------------------------------------------------
# Main execution
# ---------------------------------------------------------------------------

def main() -> int:
    """
    Execute the complete Git fundamentals curriculum.

    Each demonstration is isolated in a temporary directory. The directory
    is removed automatically when the script finishes.
    """
    global DEMO_ROOT

    check_git_available()

    with tempfile.TemporaryDirectory(prefix="git_fundamentals_") as temp_dir:
        DEMO_ROOT = Path(temp_dir)

        print(
            "\nTemporary demonstration directory:"
            f"\n{DEMO_ROOT}"
        )

        demonstrate_git_mental_model()
        demonstrate_repository_initialization()
        demonstrate_status_add_commit()
        demonstrate_diff_log_show()
        demonstrate_gitignore()
        demonstrate_branches()
        demonstrate_fast_forward_merge()
        demonstrate_three_way_merge()
        demonstrate_merge_conflict()
        demonstrate_rebase()
        demonstrate_rebase_conflict()
        demonstrate_reset_restore_revert()
        demonstrate_references_and_head()
        demonstrate_stash()
        demonstrate_tags()
        demonstrate_cherry_pick()
        demonstrate_remote_concepts()
        demonstrate_fetch_and_divergence()
        demonstrate_merge_vs_rebase()
        demonstrate_reflog_recovery()
        demonstrate_commit_design()
        demonstrate_file_operations()
        demonstrate_branch_lifecycle()
        demonstrate_common_mistakes()
        demonstrate_security()
        demonstrate_performance_and_hygiene()
        demonstrate_advanced_inspection()
        demonstrate_bisect()
        demonstrate_workflows()
        demonstrate_edge_cases()
        demonstrate_configuration()
        demonstrate_object_model()
        print_best_practices()
        print_command_reference()

        section("Curriculum completed")
        explain(
            """
            The demonstrations have covered Git from repository creation and
            basic commits through branching, merge, rebase, collaboration,
            recovery, debugging, security, and the Git object model.

            All temporary repositories are removed automatically when the
            script exits.
            """
        )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nExecution interrupted by the user.")
        raise SystemExit(130)
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
