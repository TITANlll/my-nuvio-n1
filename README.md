# My Nuvio — Build N1 (catalog-only addon)

**Status: project created and unit-tested; NOT live yet.** This zip is **not an install URL**. A working URL requires publishing the `site/` directory to a real HTTPS web host. The recommended free path is GitHub Pages. Do not paste `manifest.preview.json` or this ZIP into Nuvio.

## Build N1 contents

- All **58 approved catalog definitions** are preserved in `catalogs.json` and grouped by network/topic.
- **10 BetterPosters discovery rows** remain with the BetterPosters addon you already installed; publishing duplicate copies would clutter Nuvio.
- **3 personalized For You rows** remain with a separately connected personalization addon/account. This project does not access your viewing history.
- **20 genre/mood folder names** appear in `browsing-folders.json`. Folder navigation is a Nuvio/collection-manager feature, not a feature of the standard Stremio catalog protocol. This JSON is a planning guide, not automatically installed folders.
- The generator publishes each **additional catalog only if it can produce justified, identifiable entries**. Held catalogs are explained in `status.json` after build, rather than filled with fabricated rankings or false subscription/subtitle claims.
- Uses **official Netflix Saudi weekly Top 10** from the published country dataset. In some cases Netflix title names cannot be matched unambiguously to IMDb IDs; those chart entries are skipped, and the original rank is preserved in the description. If the data is inaccessible, it is held, *not* replaced with a fake Top 10.
- Uses **TMDB** for clearly attributed movie/TV discovery and for correctly identified movie/series IDs. Some topic-based or release-date catalogs are necessarily *curated/approximate*, not original service lists.
- Curated source-verified awards and mature animation entries are seeded in `data/verified.json`. Shahid exclusives and Turkish Arabic-subtitle titles are intentionally withheld until each title is documented with source URLs; there is **no fabricated Shahid Top 10**.
- **Playback remains separate:** AIOStreams, Turkish streaming addons, subtitle addons and Nuvio itself handle streams, subtitles, Library and Continue Watching.

## Publish free with GitHub Pages

1. Create a **public** GitHub repository called `my-nuvio-n1`, using your own GitHub account.
2. Unzip this project. Upload **its contents**, not the `.zip` as one file, to the repository root, preserving `.github/workflows/deploy.yml`, `data/verified.json`, `catalogs.json`, and `generate.py`.
3. Get a free personal **TMDB API Read Access Token** via https://www.themoviedb.org/settings/api . Read TMDB's usage/attribution terms.
4. In GitHub: **Repository → Settings → Secrets and variables → Actions → New repository secret**. Name it `TMDB_BEARER_TOKEN` and paste the token. Do not put the token in any public file or send it in chat.
5. Under **Repository → Settings → Pages**, set the build source to **GitHub Actions**.
6. Under **Repository → Actions → Publish My Nuvio Build N1**, choose **Run workflow**. If GitHub requests that workflows be enabled, enable them for your own repository. The workflow also schedules a daily refresh.
7. Check that the workflow succeeds and that **Pages** provides a real website URL. The install address is your website URL followed by `/manifest.json` — generally `https://YOUR_USERNAME.github.io/my-nuvio-n1/manifest.json`, but use the URL GitHub actually assigns.
8. On the Sony TV: **Nuvio → Settings → Addons → Install / Add by URL**, then paste your *live* HTTPS `manifest.json` URL. If your version organizes those menus differently, use the addon URL entry screen.

**BetterPosters badges:** Your existing BetterPosters addon keeps its own badges and discovery lists. This project uses normal TMDB posters unless you set an optional secret `BETTERPOSTERS_POSTER_PATTERN` using the **actual URL pattern supplied by your BetterPosters configurator**, containing `{imdb_id}` or `{id}`. Do not guess an undocumented endpoint. Depending on Nuvio's metadata/poster priority, another installed addon may override these posters; this must be tested on the Sony TV.

## Current accuracy boundaries

| Item | Data / implementation status |
|---|---|
| Netflix Saudi weekly Top 10 movies and TV | Official TSV, names mapped conservatively to IMDb; not real-time daily |
| Netflix Saudi other discovery | TMDB Saudi availability/popularity and recent *production* dates, not an exact Netflix “Newly Added” feed |
| Shahid Arabic exclusives and VIP | Requires separately verified title-level evidence (not currently automated) |
| Turkish content with Arabic subtitles | Requires separately verified title-level evidence (not currently automated) |
| BetterPosters 10 discovery catalogs | Kept separate; already provided by BetterPosters |
| Family & Kids | Strict G/TV-Y-type ratings when available; age labels alone cannot guarantee suitability, and filtering isn't parental control |
| Awards/Adult animation | Curated examples with evidence; expand the verified list over time |
| Documentaries/Currently Airing | TMDB classifications and date/episode metadata, not proof that a video is already playable |
| Trakt personal recommendations | Existing separately connected addon/account required; not scraped or redistributed |
| Genres & Moods folders | Planning labels; Nuvio collection placement must be configured in app or collection manager |

## Files

- `catalogs.json` — all 58 frozen Build N1 catalog definitions, with mode and source choices.
- `browsing-folders.json` — the 20 approved genre/mood labels, organized under two folder concepts.
- `data/verified.json` — curated, source-attributed IMDb items; expand only after real verification. For Turkish titles also include `origin_country: "TR"`, `original_language: "tr"`, `arabic_subtitles_verified: true`, and a `subtitle_source_url`. For Shahid, verify `original_language: "ar"` and `shahid_exclusive_verified: true` with a source.
- `generate.py` — static catalog builder using TMDB and the official Netflix TSV.
- `.github/workflows/deploy.yml` — daily automatic generation and GitHub Pages deployment.
- `tests/test_n1.py` — tests for manifest schema, 58-item plan and verification guards.
- Generated public `status.json` — which catalogs are actively published and which were held, with reason.

## Testing locally

`python -m unittest discover -s tests -v`

To generate locally, set `TMDB_BEARER_TOKEN` and `PAGE_URL` to the actual public HTTPS base URL, then run `python generate.py`. The generator uses only the Python standard library. If live source APIs cannot be accessed from the build runner, the affected catalogs remain held, not replaced with sample content.

### Attribution

This product uses the TMDB API but is not endorsed or certified by TMDB. Netflix charts are attributed to Netflix Tudum. Film and TV artwork and data are subject to third-party rights and availability.

Official technical references:
- https://stremio.github.io/stremio-addon-sdk/protocol.html
- https://zedensix.com/nuvio-web/docs/addons
- https://developer.themoviedb.org/docs/authentication-application
- https://developers.cloudflare.com/workers/configuration/secrets/
- https://www.netflix.com/tudum/top10
- https://btttr.cc/configure
