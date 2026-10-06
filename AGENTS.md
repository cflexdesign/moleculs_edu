# Course repository

The user requested that the HTML project from this task be uploaded to GitHub and that completed updates be sent there directly.

The user supplied the destination repository: `https://github.com/cflexdesign/moleculs_edu.git`. Use `origin` and branch `main` for this project. Do not publish to a different repository.

## Scope

- Course deliverables live in `outputs/`. The current entry point is `outputs/knowledge-base/index.html`; preserve relative links and media assets.
- Keep scratch files in `work/`, outside version control. Honor `.gitignore`; do not force-add ignored archives, duplicate standalone builds, credentials, or unrelated local files.
- The primary publication target for the knowledge base is now `https://moleculai.ru/knowledge-base`, through the existing Russian CMS at `https://cms.moleculai.ru`. The user explicitly authorized publishing completed updates directly there on 6 October 2026. The international CMS is outside scope.
- GitHub Pages at `https://cflexdesign.github.io/moleculs_edu/` remains the static mirror. Do not change repository visibility or deploy to unrelated hosting providers.
- GitHub Pages publishes the root of `main`. Keep the root `index.html` redirect to `outputs/knowledge-base/index.html` and `.nojekyll` in place. A successful push to `main` triggers a site update; check the Pages deployment when reporting a live-site update.

## Publish completed updates

- After completing a coherent batch of requested course edits and the relevant existing checks, inspect `git status` and the diff.
- Publish knowledge-base updates directly to the Russian CMS with `scripts/publish_kb.py`. Read `scripts/README.md` first. Validate a representative change in dev, publish production with explicit `status=published`, then check the CMS verification report and the live Russian frontend. Native CMS publication is a required part of completion, not an optional next step.
- Keep existing CMS slugs and relations stable. Do not delete pages or media. Hide merged materials from navigation and provide a link to the current instruction. Import only the public knowledge base; do not import the separate sales/team curricula without a new request.
- Credentials remain in the ignored, private `work/cms-publication/access.md`, never in source code, commands, logs, Git, exports or public pages. Pass its path with `--access-file`. CMS backups, upload manifests and publication reports stay in ignored `work/cms-publication/`.
- The CMS supports native prompts, cards, media and FAQ blocks. Do not claim static-browser progress or interactive quizzes are supported there: publish self-check questions as expandable answer explanations. Preserve the interactive static edition in GitHub Pages.
- Publication is pending until an `origin` remote has been configured and GitHub authentication works. If either is missing, report the missing setup; do not invent a remote or claim an upload succeeded.
- Once configured, stage only this task's completed course files and repository documentation. Commit with a descriptive message, then push the current branch to its configured upstream. If the upstream is not set, configure it only for the intended branch on `origin`.
- Do not commit files another process is currently writing, unrelated user changes, or incomplete work. Do not force-push, reset, discard changes, or resolve remote conflicts by overwriting them.
- If Git rejects a file because of size, stop publication and report it; do not silently remove a required asset.
- Verify the remote branch contains the new commit before reporting successful publication. If the push fails, retain the local work and report that GitHub has not been updated.

This is a workflow instruction for Codex after completed work, not a background filesystem watcher or a schedule.
