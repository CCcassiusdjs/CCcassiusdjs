# Profile setup

Steps that cannot be done from inside this repository. Do them in order — each
later step assumes the earlier ones.

## 1. Personal access token (the only hard requirement)

<https://github.com/settings/tokens> → **Generate new token (classic)** → scopes:

| Scope | Without it |
| --- | --- |
| `repo` | private repositories vanish from the activity overview |
| `read:org` | the `lsa-pucrs` panel comes back empty |

Add it to this repository under **Settings → Secrets and variables → Actions**
as **`PROFILE_TOKEN`**. Two workflows read it: `activity-overview.yml` and
`profile-3d.yml`.

`activity-overview.yml` fails loudly when the secret is missing rather than
falling back to the built-in `GITHUB_TOKEN`. That fallback would authenticate as
the repository, which sees neither private repositories nor organization work,
and would publish quietly deflated numbers — worse than publishing nothing.

Set an expiry you will actually renew. When it lapses the workflow fails, which
is the failure mode you want; stale figures would not announce themselves.

## 2. Publish private contributions

<https://github.com/settings/profile> → **Contributions** → tick
**Include private contributions on my profile**.

This does *not* affect the activity overview — those numbers already include
private work, because the token from step 1 authenticates as you. It affects the
things GitHub itself renders from the public view: the contribution graph on your
profile page, the streak card, the snake, and the 3D calendar. It publishes counts
and dates only, never repository names, never code.

While in there, **Contribution settings → Activity overview** turns on GitHub's
own radar on the profile page. `assets/activity-overview-*.svg` reproduces that
widget for the README, since the native one cannot be embedded.

## 3. First run

Both generators are idempotent — they commit only when the rendered output
actually changed.

```bash
gh workflow run activity-overview.yml
gh workflow run profile-3d.yml
gh run watch
```

`profile-3d.yml` writes `profile-3d-contrib/*.svg`. Once those exist, uncomment
the 3D block near the bottom of `README.md` — it 404s until then.

## 4. Populate ORCID

<https://orcid.org/0000-0001-6803-5638> currently lists **zero works**; the API
returns `"group": []`. The Publications section shows a placeholder sentence
until that changes.

ORCID imports from Crossref, Scopus and DataCite, so most entries need no typing.
`orcid-publications.yml` runs weekly and rewrites the section between the
`ORCID-LIST` markers. To see it immediately:

```bash
gh workflow run orcid-publications.yml
```

ORCID publishes no RSS or Atom feed, which is why `.github/scripts/orcid_publications.py`
queries `pub.orcid.org/v3.0` rather than using an off-the-shelf feed action.

## What runs without any setup

The snake (`snake.yml`, 12-hour cron, publishing to the `output` branch), the
streak card, the header banner, the typing animation, the skill icons, and every
shields.io badge.

## Why there is no Vercel deployment here

The usual profile cards are hosted SVG services, and the three most common ones
were dead — not throttled — when this profile was built on 2026-08-30:

| Service | Response |
| --- | --- |
| `github-readme-stats.vercel.app` | `503 DEPLOYMENT_PAUSED` |
| `github-readme-activity-graph.vercel.app` | `402 DEPLOYMENT_DISABLED` |
| `github-profile-trophy.vercel.app` | `402 DEPLOYMENT_DISABLED` |

Self-hosting forks of all three would have meant three Vercel projects to keep
alive. Generating the SVG in a workflow instead removes the dependency entirely,
and is the only approach that reaches private and organization contributions
without handing a token to a third-party host.

## Maintenance

Third-party image hosts fail silently — GitHub's camo proxy caches the last good
response, so a dead service can look fine for days. Every few months, or any time
the profile looks off, re-check the remaining external images:

```bash
grep -oE 'https://[^"<>)]+' README.md | grep -E 'demolab|skillicons|shields|capsule' \
  | sort -u | xargs -I{} sh -c 'printf "%s %s\n" "$(curl -s -o /dev/null -w %{http_code} -L --max-time 20 "{}")" "{}"'
```

Anything that is not `200` should be commented out rather than left broken.
