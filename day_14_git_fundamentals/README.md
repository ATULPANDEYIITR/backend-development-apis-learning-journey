# Git fundamentals

## Introduction

Git is a distributed version-control system used to record changes to files, maintain multiple lines of development, compare versions, recover earlier states, and coordinate work between developers.

A Git repository contains a history of committed project states. Developers normally work with three important areas:

- The working tree contains the files currently present on disk.
- The staging area, also called the index, contains the exact snapshot selected for the next commit.
- The repository contains committed history and Git's internal objects and references.

Understanding the distinction between these areas is the foundation of effective Git usage.

The accompanying Python script provides executable demonstrations using temporary repositories. It covers basic repository operations and progresses through branches, merging, rebasing, remotes, recovery, debugging, security, and Git's internal object model.

## Git terminology

### Repository

A repository is the complete Git-managed history and metadata for a project. A normal working repository contains a `.git` directory alongside the project files.

A repository can be local or remote. A local repository contains the developer's working tree and local Git database. A remote repository is another repository used for sharing and collaboration.

### Working tree

The working tree is the collection of project files currently checked out on disk.

Changes made with an editor normally begin in the working tree. Git does not automatically place every working-tree change into the next commit.

### Staging area

The staging area is an intermediate snapshot between the working tree and the repository.

The command `git add` updates the staging area. This means that `git add` does not mean "save everything permanently." It means "select this version of this path for the next commit."

This distinction permits several unrelated modifications to exist in the working tree while only selected changes are included in a commit.

### Commit

A commit records a project snapshot together with metadata such as author information, timestamps, a message, and references to parent commits.

A commit normally points to one parent. A merge commit can have two or more parents.

Each commit has an object identity derived from its contents and metadata. Consequently, changing a commit's contents or ancestry produces a different commit identity.

### Branch

A branch is a movable reference to a commit.

Creating a branch is inexpensive because Git does not normally copy the entire project. A branch reference points to a commit and moves forward when new commits are created on that branch.

For example, a project may contain:

`main -> A -> B -> C`

A feature branch created at `B` may produce:

`main -> A -> B -> C`

`feature -> A -> B -> D`

The two branch references point to different tips while sharing the earlier history.

### HEAD

`HEAD` identifies the currently checked-out position.

When a normal branch is checked out, HEAD generally points symbolically to that branch. The branch then points to the current commit.

Detached HEAD occurs when HEAD points directly to a commit rather than to a branch reference.

### Remote

A remote is a named reference to another repository. `origin` is the conventional name assigned to the primary remote when a repository is cloned.

Remote operations commonly include fetching, pulling, and pushing.

### Remote-tracking branch

A reference such as `origin/main` represents the state of the remote branch as last known to the local repository.

It is not the same as the local `main` branch.

`git fetch` updates remote-tracking references without automatically changing the current local branch.

## Initializing and cloning repositories

A new local repository can be created with `git init`.

A repository can be copied from an existing remote using `git clone`.

The Python demonstration initializes several temporary repositories and configures a local username and email inside each repository. Repository-local configuration prevents the examples from depending on the developer's global Git identity.

A normal Git repository contains a `.git` directory. This directory contains Git's internal database, references, configuration, and other metadata.

Deleting `.git` does not normally delete the ordinary project files, but it removes the local Git repository metadata and therefore should never be done casually.

## The basic Git workflow

A fundamental workflow is:

1. Inspect the repository with `git status`.
2. Modify files in the working tree.
3. Inspect modifications with `git diff`.
4. Stage selected changes with `git add`.
5. Inspect the staged snapshot with `git diff --cached`.
6. Create a commit with `git commit`.
7. Inspect history with `git log`.

The important transition is:

`working tree -> staging area -> commit`

The staging area allows the developer to decide exactly what belongs in a commit.

## `git status`

`git status` describes the relationship between the working tree, staging area, and current branch.

Typical categories include:

- Untracked files
- Modified but unstaged files
- Modified and staged files
- Deleted files
- Renamed files
- Branch and remote-tracking information

Using the short form, `git status --short`, produces a compact representation useful during routine development.

Checking status before significant Git operations is a practical habit because many Git errors are caused by misunderstanding the current branch or the current staging state.

## `git add`

`git add` places the current contents of selected paths into the staging area.

For example:

`git add app.py`

stages the current version of `app.py`.

`git add -A`

stages additions, modifications, and deletions throughout the repository.

A subtle but important behavior is that staging captures the file state at the moment `git add` executes. If the file is modified again afterward, the new modification remains unstaged.

The Python script demonstrates this state explicitly by staging a file and then modifying it again before committing.

## `git commit`

A commit records the staged snapshot.

A typical command is:

`git commit -m "Add validation"`

A good commit message describes the meaningful change represented by the commit.

Focused commits are easier to review, debug, revert, cherry-pick, and understand later.

A commit should ideally represent one coherent unit of work rather than a mixture of unrelated changes.

## Differences between `git diff` commands

The location of the comparison matters.

`git diff`

compares the working tree with the staging area.

`git diff --cached`

compares the staging area with the current commit.

`git diff HEAD`

compares the working tree and staging area together against HEAD.

This distinction is one of the most important practical Git concepts because it explains why a commit can contain less than what is currently visible in the working directory.

## Git history

`git log` displays commit history.

Useful options include:

`--oneline`

Displays compact commit identifiers and messages.

`--graph`

Displays branch and merge relationships graphically.

`--decorate`

Displays references such as branches and tags.

`--all`

Includes history reachable from all local references.

A useful inspection form is:

`git log --oneline --graph --decorate --all`

The history is fundamentally a graph rather than simply a list. Branching creates multiple paths through that graph, and merging can join those paths.

## `git show`

`git show` displays information about an object, commonly a commit.

It can show:

- Commit metadata
- Commit message
- Parent information
- Changed files
- Patch content

Using `git show --stat` is useful when only a summary of changed files is required.

## `.gitignore`

A `.gitignore` file defines patterns for paths that Git should normally treat as ignored when they are untracked.

Common examples include:

- Python bytecode
- Virtual environments
- Build output
- Operating-system metadata
- Local environment configuration

A `.gitignore` rule does not erase previously committed content.

If a file has already been committed, adding that filename to `.gitignore` does not cause Git to stop tracking it automatically.

A tracked file can be removed from the index while retained locally with an operation such as:

`git rm --cached filename`

The file can then remain ignored.

### `.gitignore` and secrets

`.gitignore` is not a secret-management system.

It can reduce the chance of accidentally staging local configuration files, but it does not protect a secret that has already been committed.

If a password, private key, API token, or other credential is committed, the credential should be revoked or rotated immediately. Removing the file from the latest snapshot does not make historical exposure disappear.

## Branches

Branches allow multiple lines of development to exist in the same repository.

A common workflow is to create a feature branch from `main`:

`git switch -c feature/login`

Development commits then move the feature branch forward without changing `main`.

Switching branches changes the working-tree snapshot to match the selected branch.

Useful commands include:

`git branch`

Lists branches.

`git branch --show-current`

Displays the current branch.

`git switch branch-name`

Switches to an existing branch.

`git switch -c branch-name`

Creates and switches to a new branch.

## Fast-forward merges

A fast-forward merge occurs when the target branch has not diverged from the branch being merged.

Suppose history is:

`A -> B -> C`

and `main` points to `B` while `feature` points to `C`.

Merging `feature` into `main` can simply move the `main` reference from `B` to `C`.

No merge commit is required because there is no independent mainline history to combine.

The command:

`git merge --ff-only feature`

can require this behavior and fail if a fast-forward is impossible.

## Three-way merges

A three-way merge becomes necessary when two branches have independently advanced.

For example:

`A -> B -> C` on `main`

and:

`A -> B -> D` on `feature`

The merge operation considers:

- The common ancestor `B`
- The current branch tip `C`
- The incoming branch tip `D`

Git combines the changes introduced on the two branches.

If those changes do not conflict, Git can automatically construct the merged result.

If they overlap incompatibly, a conflict must be resolved manually.

## Merge conflicts

A merge conflict occurs when Git cannot determine a single correct result from the changes being combined.

A common conflict representation contains markers such as:

`<<<<<<<`

`=======`

`>>>>>>>`

These markers identify the competing versions.

The correct resolution process is:

1. Inspect the conflicting file.
2. Understand the intent of both changes.
3. Edit the file into the desired final state.
4. Remove the conflict markers.
5. Stage the resolved file with `git add`.
6. Complete the merge commit.

A conflict is not necessarily a Git failure. It means automated integration could not safely determine the desired result.

After resolving a conflict, tests should be run because syntactic resolution does not guarantee semantic correctness.

## Rebase

Rebase moves a sequence of commits onto a different base.

Suppose:

`A -> B -> C` is `main`

and:

`A -> B -> D` is `feature`.

Rebasing `feature` onto `main` conceptually produces:

`A -> B -> C -> D'`

`D'` is not the same commit object as the original `D`. It is a newly created commit representing the replayed change.

This is why rebase is history rewriting.

Rebase can produce a linear history that is easier to inspect, but it must be used carefully when commits have already been shared.

## Merge versus rebase

Merge preserves the existing branch topology.

Rebase reconstructs commits on top of another base.

| Operation | Main effect | Important property |
|---|---|---|
| Merge | Combines histories | Preserves existing commit identities |
| Rebase | Replays commits onto another base | Creates new commit identities |
| Cherry-pick | Applies one commit's change elsewhere | Creates a new commit |
| Revert | Adds an inverse change | Preserves existing history |
| Reset | Moves a reference and optionally index or working tree | Can rewrite local branch history |
| Restore | Restores file content | Primarily works with working tree and index |

A private feature branch that has not been shared can often be rebased safely.

A shared branch should not normally be rebased casually because other developers may already have references to the old commit identities.

The choice is a workflow decision rather than a universal rule that one operation is always superior.

## Rebase conflicts

A rebase can also produce conflicts.

The usual process is:

1. Inspect the conflicting files.
2. Resolve the desired final content.
3. Stage the resolution.
4. Run `git rebase --continue`.

If the rebase should be abandoned:

`git rebase --abort`

returns the branch to the state from before the rebase began.

Rebase conflicts can be more complex than merge conflicts because the operation is replaying individual commits sequentially.

## `git restore`

`git restore` is primarily concerned with file content.

For example:

`git restore file.txt`

can restore the working-tree version from the index.

`git restore --staged file.txt`

can remove staged changes from the index while retaining the working-tree modification.

This command provides a clearer separation of file-content restoration from reference movement than older workflows that relied heavily on `git checkout`.

## `git reset`

`git reset` can move the current branch reference and, depending on its mode, modify the staging area and working tree.

### Soft reset

`git reset --soft <commit>`

moves the branch reference while leaving the index and working tree intact.

This is useful when commits need to be reorganized locally while retaining the staged content.

### Mixed reset

`git reset <commit>`

uses mixed behavior by default. It moves the branch reference and resets the index while leaving working-tree files in place.

### Hard reset

`git reset --hard <commit>`

moves the branch reference and resets both the index and working tree to match the specified commit.

This can discard uncommitted changes and therefore requires extreme care.

Reset is generally most appropriate for local history manipulation where rewriting history is acceptable.

## `git revert`

`git revert <commit>` creates a new commit that reverses the changes introduced by another commit.

This is fundamentally different from reset.

Reset changes where a branch reference points.

Revert preserves the original history and adds another commit.

For shared branches, revert is usually safer when a previously published change needs to be undone.

## HEAD and revision expressions

Git provides revision syntax for navigating history.

`HEAD`

refers to the current checkout position.

`HEAD~1`

refers to the first-parent ancestor one generation earlier.

`HEAD~2`

moves two generations backward through the first-parent chain.

`HEAD^`

selects the first parent.

For a simple linear history, `HEAD~1` and `HEAD^` commonly identify the same commit.

Merge commits make parent selection more important because they can have multiple parents.

## Detached HEAD

A detached HEAD occurs when Git checks out a commit directly instead of checking out a branch reference.

This is useful for:

- Inspecting historical versions
- Running tests against old commits
- Comparing behavior
- Temporarily experimenting with an old state

If meaningful commits are created in detached HEAD state without a branch or tag preserving them, those commits can eventually become difficult to locate.

A branch can be created to preserve the work:

`git switch -c recovery-branch`

## Stash

The stash mechanism temporarily stores local changes.

A common command is:

`git stash push -u -m "Work in progress"`

The `-u` option includes untracked files.

`git stash list`

shows stored stashes.

`git stash pop`

restores the most recent stash and normally removes it from the stash list after successful application.

Stash is useful for temporary context switching, but permanent development work is generally better represented by meaningful commits.

## Tags

Tags identify important points in history.

They are commonly used for releases such as:

`v1.0.0`

Two important forms are lightweight tags and annotated tags.

A lightweight tag is a simple reference.

An annotated tag is a Git object containing metadata such as the tagger, date, and message.

Annotated tags are generally more suitable for formal release identification.

## Cherry-pick

Cherry-pick applies the change introduced by an existing commit onto the current branch.

For example:

`git cherry-pick <commit>`

The resulting commit has a different identity from the source commit because it is a new commit in a different history context.

Cherry-pick is useful when a specific fix needs to be transferred without merging an entire feature branch.

It can also produce conflicts when the selected change does not apply cleanly to the destination branch.

## Remote repositories

Remote repositories allow Git histories to be shared between environments.

Common operations include:

`git fetch`

Downloads remote objects and updates remote-tracking references without integrating them into the current branch.

`git pull`

Typically performs a fetch followed by an integration operation. The integration behavior can involve merge or rebase depending on configuration and options.

`git push`

Sends local commits and related objects to the remote and attempts to update the corresponding remote branch.

`git remote -v`

Displays configured remote names and URLs.

`git push -u origin feature`

pushes the feature branch and establishes its upstream relationship with `origin/feature`.

## Non-fast-forward pushes

A push can be rejected when the remote branch contains commits that the local branch does not contain.

This usually indicates that histories have diverged.

A safe response is to:

1. Fetch remote history.
2. Inspect the divergence.
3. Integrate the remote changes through an appropriate merge or rebase.
4. Resolve conflicts if required.
5. Test the result.
6. Push again.

Force-pushing should not be used as a generic solution to rejected pushes.

## `origin/main` versus `main`

These references have different meanings.

`main`

is a local branch.

`origin/main`

is a remote-tracking reference representing the locally recorded state of the remote's `main` branch.

Fetching updates `origin/main`.

It does not automatically move local `main`.

This distinction is essential when inspecting whether the local branch is ahead, behind, or diverged from a remote branch.

## Commit design

A useful commit is:

- Coherent
- Reviewable
- Testable
- Described accurately
- Small enough to understand
- Independent where practical

Focused commits make it easier to identify regressions and reverse individual changes.

For example, separating an implementation change from unrelated documentation changes can make review and future history analysis clearer.

The staging area is particularly useful when the working tree contains several unrelated changes.

## File operations

Git can track:

- New files
- Modified files
- Deleted files
- Renamed files
- Copies and related content changes

`git mv` provides a convenient rename workflow.

Git's internal model is snapshot-oriented. Rename detection is largely an interpretation based on similarity between file contents and paths rather than a primitive requirement that every rename be stored as a special rename object.

This is why Git can often recognize a rename even when ordinary filesystem commands were used followed by staging.

## Empty directories

Git tracks files rather than empty directories.

An empty directory by itself does not create a Git-tracked directory entry.

Projects that need to preserve an otherwise-empty directory sometimes place a deliberate placeholder file inside it. That is a project convention rather than a special Git mechanism.

## Line endings

Operating systems commonly use different line-ending conventions.

Unix-like systems commonly use LF.

Windows commonly uses CRLF.

Git can normalize line endings through configuration and `.gitattributes`.

An explicit `.gitattributes` policy can make cross-platform behavior more predictable.

For example, a project may define automatic text normalization while requiring shell scripts to use LF.

## Case sensitivity

Filesystem case sensitivity varies between operating systems and filesystems.

A filename such as `Data.txt` can behave differently from `data.txt` depending on the environment.

Cross-platform repositories should avoid relying on ambiguous case-only filename differences because a change that behaves normally on one filesystem can be confusing or problematic on another.

## Binary files

Text files can normally be compared line by line.

Binary files do not generally provide meaningful ordinary text diffs.

Large binary files can also have significant repository-size consequences because ordinary Git history retains historical objects even after a file is removed from the latest snapshot.

Repositories containing substantial binary artifacts require deliberate storage and maintenance strategies.

## Reflog

The reflog records movements of local references such as HEAD.

It is especially valuable after accidental local operations such as:

- Resetting a branch too far
- Moving a branch reference
- Rebasing
- Switching between commits

A typical recovery process is:

1. Run `git reflog`.
2. Identify the desired commit.
3. Create a recovery branch at that commit.

For example:

`git switch -c recovery <commit>`

The reflog is local and should not be considered a replacement for a remote backup.

Reflog entries are also subject to expiration and repository maintenance, so recovery should not be postponed unnecessarily.

## `git bisect`

`git bisect` uses binary search to identify the commit that introduced a regression.

The developer identifies:

- A known-good commit
- A known-bad commit

Git selects an intermediate commit.

The developer tests that commit and reports it as good or bad.

Git then narrows the search range.

If there are approximately `N` candidate commits, binary search requires roughly logarithmic numbers of tests rather than checking every commit sequentially.

This makes bisect particularly useful when a bug's exact introduction point is unknown but the behavior can be tested reliably at individual revisions.

Automation is especially powerful when the project has a deterministic test command that can return success or failure.

## Advanced history inspection

### `git rev-parse`

`git rev-parse` resolves revision expressions and can also report repository paths.

It is useful in scripts and advanced Git diagnostics.

### `git cat-file`

`git cat-file` exposes Git's low-level object model.

It can identify object types and display their contents.

This is useful for understanding what Git actually stores rather than viewing the repository only through high-level commands.

### `git blame`

`git blame` associates lines with commits and authors.

It is most useful for finding historical context around a line.

It should not be interpreted as a mechanism for assigning personal fault.

### Search by content change

`git log -S <text> -- <file>`

finds commits where the number of occurrences of a string changes.

`git log -G <regex> -- <file>`

searches for changes matching a regular expression.

These commands are useful for locating the historical introduction or removal of behavior.

## Git's object model

Git's core object model includes blobs, trees, commits, and annotated tag objects.

### Blob

A blob stores file content.

The blob itself does not inherently represent a filename.

### Tree

A tree represents a directory snapshot and maps names to blobs or other trees.

It provides the structure required to reconstruct a project snapshot.

### Commit

A commit points to a tree and records metadata and parent relationships.

A normal commit has one parent.

A root commit has no parent.

A merge commit can have multiple parents.

### Tag object

An annotated tag object provides metadata around another Git object.

### References

Branches and tags are references that point to Git objects.

This design explains why creating a branch is inexpensive. A branch is primarily a reference to an existing commit rather than a complete copy of the repository.

## Security considerations

Git security is closely related to repository content and history.

### Never commit credentials

Credentials that should not be committed include:

- Passwords
- Private keys
- API tokens
- Access tokens
- Database credentials
- Cloud credentials
- Signing secrets

Use secure configuration mechanisms appropriate to the deployment environment.

### `.gitignore` is not security

Ignoring `.env` does not protect a `.env` file that was already committed.

A credential that entered Git history should be considered exposed.

The immediate security response is credential rotation or revocation.

History rewriting may be required for repository hygiene, but it does not undo external exposure.

### Review before commit

Review both:

`git diff`

and:

`git diff --cached`

The first identifies unstaged working-tree changes.

The second identifies the exact content prepared for the next commit.

This review can catch credentials, debugging statements, accidental files, and unrelated modifications.

### Verify remotes

Before pushing important work, inspect:

`git remote -v`

This helps prevent accidentally sending content to the wrong destination.

### Force pushes

Force-pushing changes remote branch history and can disrupt other developers.

If a workflow genuinely requires rewriting shared history, the team should have an explicit policy and use safer force-push mechanisms where appropriate.

### Hooks

Git hooks can execute commands automatically.

Repositories obtained from unfamiliar sources should be treated as potentially executable code. Developers should understand what repository-specific scripts and hooks do before running them.

## Performance considerations

Git is designed to work efficiently with snapshots, content-addressed objects, compression, and indexes.

Repository size can still become a practical problem.

Common causes include:

- Large generated artifacts
- Large binary files
- Frequently changing generated data
- Long histories containing unnecessary objects
- Repeatedly rewriting large histories

Useful practices include:

- Ignore reproducible build output.
- Avoid committing unnecessary generated files.
- Keep large binary artifacts under appropriate storage policies.
- Use shallow or partial cloning when justified.
- Maintain focused repository content.
- Understand repository maintenance before pruning objects.

Commands such as `git count-objects -v`, `git gc`, and `git fsck` can assist with repository inspection and maintenance.

Maintenance operations that remove unreachable objects should be used carefully when recovering accidentally discarded work.

## Common mistakes

### Forgetting to stage changes

Running `git commit` does not automatically stage every modification.

The staging area determines the contents of the next commit.

### Working on the wrong branch

Before substantial changes, inspect:

`git status`

and:

`git branch --show-current`

This prevents many accidental commits to the wrong branch.

### Assuming `.gitignore` removes tracked files

It does not.

A tracked file remains tracked until it is removed from the index.

### Using reset carelessly

`git reset --hard` can destroy uncommitted working-tree and staged changes.

It should not be treated as a harmless undo command.

### Rebasing shared commits

Rebase changes commit identities.

Rebasing a shared history can create confusing duplicate histories and force other developers to reconcile rewritten commits.

### Treating stash as permanent storage

Stashes are useful temporary workspaces, not an ideal replacement for intentional commits.

### Force-pushing to solve every problem

A rejected push normally indicates that history needs inspection and integration. Force-pushing without understanding the divergence can destroy remote history.

### Resolving conflicts mechanically

Choosing one side of every conflict without understanding the application behavior can produce code that merges successfully but is logically incorrect.

## Practical workflow

A disciplined feature workflow can be expressed as:

`status -> branch -> edit -> diff -> add -> diff --cached -> commit -> fetch -> integrate -> test -> push`

A typical sequence is:

`git status`

`git switch -c feature/name`

Edit the required files.

`git diff`

`git add <files>`

`git diff --cached`

`git commit -m "Describe focused change"`

`git fetch origin`

Inspect the remote state and integrate according to the team's merge or rebase policy.

Run tests.

`git push -u origin feature/name`

The exact workflow depends on the team's collaboration model, but the core principles remain consistent: inspect state, create deliberate commits, review staged content, integrate carefully, resolve conflicts intentionally, and test after history-changing operations.

## Merge and rebase decision guide

Use merge when preserving existing branch topology is useful or when a shared history should be integrated without rewriting existing commits.

Use rebase when a private or controlled branch needs a different base and rewriting the branch's commit identities is acceptable.

Use cherry-pick when a specific commit needs to be transferred without bringing an entire branch.

Use revert when a published change needs to be undone while preserving the historical record.

Use reset when local history needs to be moved and rewriting is acceptable.

Use restore when the main goal is to restore file content or modify the staging state.

## Release workflow

Tags can identify stable release points.

A formal release can be represented by an annotated tag such as:

`v1.0.0`

Tags provide stable names for commits even when branches continue moving.

A release process commonly involves completing and testing the intended commit, creating the release tag, and publishing the tag according to the project's release policy.

## Repository hygiene

A maintainable repository generally benefits from:

- Clear commit history
- Appropriate ignore rules
- Minimal generated content
- Explicit line-ending policy when cross-platform behavior matters
- Focused branches
- Meaningful commit messages
- Controlled remote access
- Protected important branches
- Regular review of large or unnecessary files

Repository hygiene is partly a technical concern and partly a collaboration concern. A repository is easier to maintain when its history communicates the evolution of the project clearly.

## Important distinctions

| Concept | Meaning |
|---|---|
| Working tree | Files currently present on disk |
| Index | Snapshot prepared for the next commit |
| Commit | Recorded project snapshot with history metadata |
| Branch | Movable reference to a commit |
| HEAD | Current checkout position |
| Remote | Named connection/reference to another repository |
| `origin/main` | Local remote-tracking reference |
| Merge | Integrates existing histories |
| Rebase | Replays commits onto a new base |
| Reset | Moves a reference and optionally index/worktree |
| Restore | Restores file content |
| Revert | Adds an inverse commit |
| Stash | Temporarily stores local changes |
| Tag | Named reference to an important object |
| Cherry-pick | Applies one commit's change elsewhere |
| Reflog | Records local reference movements |
| Bisect | Binary-searches history for a regression |

## Core command reference

### Repository operations

`git init`

Create a new repository.

`git clone <url>`

Copy an existing repository.

### Inspection

`git status`

Inspect current repository state.

`git log --oneline --graph --decorate --all`

Inspect commit history and branch relationships.

`git diff`

Inspect unstaged changes.

`git diff --cached`

Inspect staged changes.

`git show <commit>`

Inspect a commit.

### Staging and commits

`git add <path>`

Stage a path.

`git add -A`

Stage all relevant changes.

`git commit -m "message"`

Create a commit.

### Branches

`git branch`

List branches.

`git switch -c <branch>`

Create and switch to a branch.

`git switch <branch>`

Switch branches.

`git branch -d <branch>`

Delete a merged branch.

### Integration

`git merge <branch>`

Merge another branch.

`git rebase <branch>`

Replay the current branch's commits onto another base.

`git cherry-pick <commit>`

Apply one commit's change to the current branch.

### Undo and recovery

`git restore <path>`

Restore working-tree content.

`git restore --staged <path>`

Unstage a path.

`git reset --soft <commit>`

Move the branch reference while preserving index and working-tree content.

`git reset <commit>`

Move the branch reference and reset the index while retaining working-tree changes.

`git reset --hard <commit>`

Move the branch reference and reset the index and working tree.

`git revert <commit>`

Create a new commit that reverses another commit.

`git reflog`

Inspect local reference movements.

### Remote operations

`git remote -v`

Inspect configured remotes.

`git fetch origin`

Download remote updates without integrating them.

`git pull`

Fetch and integrate remote changes.

`git push`

Send local commits to a remote.

`git push -u origin <branch>`

Push a branch and establish its upstream relationship.

### Temporary work

`git stash push -u -m "message"`

Store tracked and untracked work temporarily.

`git stash list`

List stashes.

`git stash pop`

Apply and remove the latest stash.

### Tags and debugging

`git tag`

List tags.

`git tag -a <tag> -m "message"`

Create an annotated tag.

`git blame <file>`

Inspect line-level historical attribution.

`git log -S <text> -- <file>`

Find changes involving a specific string.

`git log -G <regex> -- <file>`

Find changes matching a regular expression.

`git bisect start`

Start a binary search through history.

## Implementation scope of the Python study script

The accompanying script deliberately uses Python's standard library and the installed Git executable.

It creates isolated temporary repositories for:

- Repository initialization
- Staging and committing
- Diff inspection
- `.gitignore`
- Branch creation
- Fast-forward merging
- Three-way merging
- Merge conflicts
- Rebasing
- Rebase conflicts
- Reset, restore, and revert
- HEAD and detached HEAD
- Stashing
- Tags
- Cherry-picking
- Bare repositories and remotes
- Fetching and divergent collaboration
- Reflog recovery
- Commit design
- File operations
- Branch lifecycle
- Security examples
- Repository inspection
- Bisect-based regression debugging
- Line-ending policy
- Git configuration
- Low-level Git objects

Because the demonstrations use temporary directories, they do not require the user's existing project to be a Git repository and do not intentionally modify the user's existing files.

The script requires Git to be installed and available through the system PATH.
