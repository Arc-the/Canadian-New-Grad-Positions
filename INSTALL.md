# Canada-only New Grad Positions overlay

This overlay keeps the upstream `listings.json` database intact while rendering
only active Canadian jobs in `README.md`.

## What it does

1. Pulls the newest `listings.json` from the upstream `dev` branch every Monday.
2. Filters the generated README to Canadian locations only.
3. Checks active Canadian posting URLs.
4. Marks a posting inactive only for strong closure signals:
   - HTTP 404 or 410
   - an explicit expired/filled/no-longer-available message
   - a redirect to a clearly closed-job URL path
5. Leaves 403, 429, 5xx, timeouts, DNS failures, and bot challenges active.
6. Uploads a detailed JSON report to each GitHub Actions run.

Closed jobs are logically removed from the README by setting `active: false`.
They are not permanently deleted from the source database.

## Install

From the root of your fork:

```bash
unzip canada-new-grad-overlay.zip
git add .github INSTALL.md
git commit -m "feat: Canada-only weekly job tracker"
git push origin dev
```

The ZIP contains paths rooted at `.github/`, so extracting it into the repository
replaces the existing README generator workflow and adds the weekly checker.

## Required GitHub settings

- The scheduled workflow must exist on the repository's **default branch**.
  The supplied workflow checks out and pushes `dev`, so the simplest setup is
  to make `dev` the fork's default branch.
- In **Settings → Actions → General → Workflow permissions**, allow read/write
  access when repository or organization policy otherwise restricts the token.
  The workflow itself requests only `contents: write`.

## First run

Open **Actions → Weekly Canada Job Refresh → Run workflow**.

Review:

- the regenerated `README.md`;
- the run summary;
- the `canada-job-check-report` artifact.

## Adjusting location matching

Edit `.github/scripts/canada_filter.py`.

Ambiguous city-only names such as London, Cambridge, Windsor, Hamilton,
Richmond, Surrey, and Victoria are deliberately excluded unless the location
also includes Canada or a province.

## Adjusting closure detection

Edit `CLOSED_PHRASES` or `CLOSED_PATH_MARKERS` in
`.github/scripts/check_canadian_jobs.py`.

The checker is deliberately conservative to avoid deleting live jobs when a
career site blocks automated requests.
