# Nuvio Build N1 review

Review branch: `fix/pages-deployment-validation`.
Base: `7e32f6592caabce78d4c0368c7bb80270beeb484`.

## Diagnosis

- Runs 43660712102 and 43661016657 failed generation because TMDB credentials were missing.
- Run 43663221068 uploaded the Pages artifact successfully, but deploy-pages immediately found zero artifact metadata records.
- Run 43665862169 succeeded after build/deploy were separated and a fixed delay was added. The repository was already live when this task began.
- README referenced a test suite absent from the repository.
- Generator exception messages could disclose API-key-bearing request URLs to logs and public status.json. The fix reports exception types and HTTP status codes only.

## Proposed changes

- Keep separate build and deploy jobs; replace the fixed sleep with a bounded artifact metadata visibility check.
- Run offline regression tests on PRs and before production builds. PRs cannot generate or deploy.
- Derive PAGE_URL from configure-pages; scope Pages/OIDC write permissions to deployment.
- Verify the published manifest and every catalog route after deployment.
- Add 10 regression tests, a credential-free live verifier, generated-file ignores, and corrected documentation.
- Preserve catalogs.json and browsing-folders.json byte for byte. Preserve existing verified records and append documented source entries for seven previously missing rows.

## Validation

- `python -m unittest discover -s tests -v`: 15 tests passed, including the missing-row filters and source-evidence guards.
- Workflow YAML parsed; dependencies inspected; `git diff --check` passed before commit.
- `python verify_site.py https://ahmedalazahrani.github.io/my-nuvio-n1`: manifest and all 25 catalog routes verified over HTTPS.
- Live status.json: 58 planned, 25 active.
- No production API credentials were used for the offline build tests. A new credentialed production build was not run.

## Review and publication

After the account rename to TITANlll, the install URL is https://titanlll.github.io/my-nuvio-n1/manifest.json . The workflow derives the current URL from GitHub Pages configuration. The old-account URL in the validation section above records the original check before the rename.

This review branch does not deploy. Merging the reviewed PR to main activates the updated production workflow. Live verification checks endpoint validity; status.json remains the feed-level record of populated and held catalogs.

## Catalog completion changes

- Append official source evidence for Rashash, The Protector, Last Call for Istanbul, and Oppenheimer's BAFTA/Golden Globe wins. Together these qualify seven previously held rows when IMDb-to-TMDB mapping succeeds. The seeded lists are deliberately small and do not establish new/trending claims.
- Require recent (90-day) evidence for Shahid/subtitle availability; verify Saudi provider scope for Netflix-specific rows and original-production evidence for streaming originals.
- Ignore blank Saudi ratings before the existing US fallback, retaining Saudi precedence when a rating exists; increase the certification candidate pool.
- Search returning-season announcements across 60 days and confirm the next episode is a returning season premiere.
- Add stable catalog IDs/types to status.json and bump the addon version to 1.1.0.
- The 13 external-addon rows cannot be completed by changing a public static manifest. They require the corresponding addon installation or account connection in Nuvio. Several new/trending/ranked verified rows still lack qualifying evidence. No placeholder or fabricated entries are published.
