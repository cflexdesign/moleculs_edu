# Course repository

The user requested that the HTML project from this task be uploaded to GitHub and that completed updates be sent there directly.

The user supplied the destination repository: `https://github.com/cflexdesign/moleculs_edu.git`. Use `origin` and branch `main` for this project. Do not publish to a different repository.

## Scope

- Course deliverables live in `outputs/`. The current entry point is `outputs/knowledge-base/index.html`; preserve relative links and media assets.
- Keep scratch files in `work/`, outside version control. Honor `.gitignore`; do not force-add ignored archives, duplicate standalone builds, credentials, or unrelated local files.
- Continue the requested course work normally. GitHub publication does not authorize changes to repository visibility or deployment to a public website.

## Publish completed updates

- After completing a coherent batch of requested course edits and the relevant existing checks, inspect `git status` and the diff.
- Publication is pending until an `origin` remote has been configured and GitHub authentication works. If either is missing, report the missing setup; do not invent a remote or claim an upload succeeded.
- Once configured, stage only this task's completed course files and repository documentation. Commit with a descriptive message, then push the current branch to its configured upstream. If the upstream is not set, configure it only for the intended branch on `origin`.
- Do not commit files another process is currently writing, unrelated user changes, or incomplete work. Do not force-push, reset, discard changes, or resolve remote conflicts by overwriting them.
- If Git rejects a file because of size, stop publication and report it; do not silently remove a required asset.
- Verify the remote branch contains the new commit before reporting successful publication. If the push fails, retain the local work and report that GitHub has not been updated.

This is a workflow instruction for Codex after completed work, not a background filesystem watcher or a schedule.
