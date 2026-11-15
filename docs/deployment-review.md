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
- Preserve catalogs.json, browsing-folders.json, and data/verified.json byte for byte.

## Validation

- `python -m unittest discover -s tests -v`: 10 tests passed.
- Workflow YAML parsed; dependencies inspected; `git diff --check` passed before commit.
- `python verify_site.py https://ahmedalazahrani.github.io/my-nuvio-n1`: manifest and all 25 catalog routes verified over HTTPS.
- Live status.json: 58 planned, 25 active.
- No production API credentials were used for the offline build tests. A new credentialed production build was not run.

## Review and publication

The live install URL is https://ahmedalazahrani.github.io/my-nuvio-n1/manifest.json . The existing deployment returned HTTP 200 and valid addon JSON during preparation.

This review branch does not deploy. Merging the reviewed PR to main activates the updated production workflow. Live verification checks endpoint validity; status.json remains the feed-level record of populated and held catalogs.
