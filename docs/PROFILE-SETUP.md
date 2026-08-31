# Profile setup

Steps that cannot be done from inside this repository. Do them in order — each
later step assumes the earlier ones.

## 1. Publish private contributions (1 click, do this first)

<https://github.com/settings/profile> → **Contributions** → tick
**Include private contributions on my profile**.

Without it, every contribution-derived visual reads zero: the streak card, the
snake, the 3D calendar, the activity graph. This account keeps all repositories
private, so this setting is the difference between a full profile and an empty
one. It publishes counts and dates only — never repository names, never code.

## 2. Personal access token

<https://github.com/settings/tokens> → **Generate new token (classic)** →
scope **`read:user`** only. Nothing else. Copy the value once.

Two places need it:

| Where | Name | Why |
| --- | --- | --- |
| This repo → Settings → Secrets → Actions | `PROFILE_TOKEN` | `profile-3d.yml` authenticates as the repo by default and would see public contributions only |
| Vercel project env (step 3) | `PAT_1` | the stats card reads private contributions through this token |

Set an expiry you will actually renew. When it lapses the cards go blank, which
is the failure mode you want — not stale numbers.

## 3. Deploy the card services

The public instances are dead, not throttled — verified 2026-08-30:

| Service | Response |
| --- | --- |
| `github-readme-stats.vercel.app` | `503 DEPLOYMENT_PAUSED` |
| `github-readme-activity-graph.vercel.app` | `402 DEPLOYMENT_DISABLED` |
| `github-profile-trophy.vercel.app` | `402 DEPLOYMENT_DISABLED` |

So each card needs your own deployment. For every repository below: fork it,
then in Vercel choose **Add New → Project → Import** the fork, and deploy with
the default settings.

| Fork | Gives you | Env var |
| --- | --- | --- |
| [anuraghazra/github-readme-stats](https://github.com/anuraghazra/github-readme-stats) | stats card + top languages | `PAT_1` = the token from step 2 |
| [Ashutosh00710/github-readme-activity-graph](https://github.com/Ashutosh00710/github-readme-activity-graph) | 31-day activity graph | none |
| [ryo-ma/github-profile-trophy](https://github.com/ryo-ma/github-profile-trophy) | trophy row | none |

Vercel hands each project a domain such as `grs-cccassiusdjs.vercel.app`.

## 4. Switch the cards on

In `README.md`, find the block marked `THE FOUR CARDS BELOW ARE COMMENTED OUT ON
PURPOSE`. Replace the placeholders with the domains from step 3, then delete the
`<!--` opening the block and the `-->` closing it.

| Placeholder | Replace with |
| --- | --- |
| `HOST-STATS.vercel.app` | your github-readme-stats domain |
| `HOST-GRAPH.vercel.app` | your activity-graph domain |
| `HOST-TROPHY.vercel.app` | your trophy domain |

Check each URL in a browser before uncommenting. A card that answers `200` with
an SVG is working; anything else stays commented.

## 5. First run of the 3D calendar

The workflow only runs from the default branch, so merge first, then:

```bash
gh workflow run profile-3d.yml
gh run watch
```

It commits `profile-3d-contrib/*.svg`. Once those files exist, uncomment the 3D
block near the bottom of `README.md` — it 404s until then.

## 6. Populate ORCID

<https://orcid.org/0000-0001-6803-5638> currently lists **zero works**; the API
returns `"group": []`. The Publications section shows a placeholder sentence
until that changes.

Add works there — ORCID imports from Crossref, Scopus and DataCite, so most
entries need no typing. `.github/workflows/orcid-publications.yml` runs weekly
and rewrites the section between the `ORCID-LIST` markers. To see it immediately:

```bash
gh workflow run orcid-publications.yml
```

ORCID publishes no RSS or Atom feed, which is why this repository queries
`pub.orcid.org/v3.0` from `.github/scripts/orcid_publications.py` rather than
using an off-the-shelf feed action.

## What already works, with no setup

The snake (`.github/workflows/snake.yml`, already running on a 12-hour cron and
publishing to the `output` branch), the streak card, the header banner, the
typing animation, the skill icons, and every shields.io badge. All verified
`200` on 2026-08-30.

## Maintenance

Third-party image hosts fail silently — GitHub's camo proxy caches the last good
response, so a dead service can look fine for days. Every few months, or any
time the profile looks off, re-check the image URLs:

```bash
grep -oE 'https://[^"<>)]+' README.md | grep -E 'vercel|demolab|skillicons|shields' \
  | sort -u | xargs -I{} sh -c 'printf "%s %s\n" "$(curl -s -o /dev/null -w %{http_code} -L --max-time 20 "{}")" "{}"'
```

Anything that is not `200` should be commented out rather than left broken.
