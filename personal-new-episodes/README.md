# New Episodes — private MDBList Nuvio addon

**Status:** Implementation prepared, not installed or deployed by this pull request.

This is a **separate** Stremio-protocol catalog for Nuvio. It does not change
`generate.py`, `catalogs.json`, the public Nuvio GitHub Pages site, or
any Netflix/Shahid/Turkish rows.

## Behavior

- Exactly one row: **New Episodes**, intended immediately under Continue Watching.
- Uses **your existing MDBList watch history** (no new watchlist or library).
- Shows the *next unwatched episode* of an in-progress show **only if that
  episode aired during the last 7 days**.
- Newest air dates first; one poster per show; no unreleased episodes.
- If you are several episodes behind and the *next unwatched* episode is older
  than seven days, that series is not displayed. This is intentional and
  distinguishes this row from the full **Up Next** backlog.
- The row's contents change when MDBList's watch progress changes and the
  addon is reloaded by Nuvio. Air date is not a guarantee that a stream exists.

## Why separate hosting?

The existing `my-nuvio-n1` catalog is hosted as **public static files on
GitHub Pages**. Adding personal MDBList watch history to that public build
would expose what you watch. A live Worker can keep the API key secret and
respond dynamically without making watch history part of the public repo.

This addon is **not** hosted by GitHub Pages. It needs a Cloudflare Worker
(or another runtime compatible with the Worker Fetch API).

## Setup (Cloudflare Workers, after reviewing the code)

1. Create a Cloudflare account and install Node.js.
2. From this folder run `npx wrangler login` then `npx wrangler deploy`.
3. In Cloudflare Workers & Pages → **new-episodes-mdblist** → Settings →
   Variables and Secrets add **encrypted secrets**:
   - `MDBLIST_API_KEY`: your personal key from https://mdblist.com/preferences/
   - `ADDON_ACCESS_TOKEN`: a **random, private string at least 24 characters long**.
4. For Nuvio, install the generated worker URL with a private path:
   `https://YOUR-WORKER.SUBDOMAIN.workers.dev/YOUR_ADDON_ACCESS_TOKEN/manifest.json`
5. In Nuvio, open **Settings → Addons → Reorder Home Catalogs**. Enable
   **New Episodes** and put it immediately below **Continue Watching**.
6. Make sure Nuvio → Settings → Tracking → MDBList is connected and that
   MDBList is receiving watched episode updates.

**Security:** Keep the install URL and key private. Anyone who obtains the
private install URL can see the catalog; this is a personal-use addon, not
multi-user authentication. Neither secret belongs in this public GitHub repo,
a commit, a screenshot, or a chat. If you leak the URL, rotate
`ADDON_ACCESS_TOKEN` in Worker settings and reinstall the new URL.

MDBList documented endpoint: `GET /upnext?limit=100&offset=0&hide_unreleased=true`.
The endpoint returns the next **unwatched aired** episode for each
in-progress show, with `next_episode.air_date` and show IDs/posters.
This addon requests up to five pages (500 in-progress shows).

## Local tests

```bash
cd personal-new-episodes
node --test
```

The tests use dummy data and make no real MDBList requests.

## Limitations

- Newly released episodes from shows with an *older unwatched backlog* are
  not shown. Showing **every** new episode regardless of backlog requires
  a separate episode-calendar reconciliation implementation.
- Only shows present in MDBList's in-progress Up Next data are eligible.
- A partial-month gap, incorrectly mapped episode numbering, or delayed
  MDBList history sync may delay/miss a row entry.
- The user must deploy the Worker and install its addon URL separately;
  opening/merging this PR does **not** add the row to the television.
