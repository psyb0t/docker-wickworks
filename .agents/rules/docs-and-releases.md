# Docs and releases

- The documentation site is `docs/`, published by GitHub Pages from `main` at https://psyb0t.github.io/docker-wickworks/ with the Just the Docs theme (`remote_theme` pinned in `docs/_config.yml`, colors in `docs/_sass/`).
- Every page has front matter with a unique `title` and a `description` of 50 to 170 characters, and exactly one `#` heading. Keep `docs/` flat.
- Links between pages use the relative `.md` path. A link to a file outside `docs/` uses the full `https://github.com/psyb0t/docker-wickworks/blob/main/<path>` URL. Wrap code blocks containing `{{` or `{%` in `<!-- {% raw %} -->` and `<!-- {% endraw %} -->`.
- After a docs change, run `make docs` and check the output in `.testing/docs-site` before handing off.
- The README is the front door: what wickworks is, the quick start, and a Documentation section with full site URLs. Reference material (indicators, SMC outputs, the API, configuration) lives in `docs/`. Each fact has one home.
- A behavior, setting, endpoint or indicator change updates the matching docs page, `schema.json`, `metadata.py`, the skill and the plugin README in the same change.
- Prose: no em dashes, "directory" never "folder", no AI vocabulary, sentence case headings, one paragraph per source line. Do not mention local scratch directories in committed text.
- CHANGELOG entries use the `## vX.Y.Z (YYYY-MM-DD)` heading and are written at release time. Pre-1.0, a minor bump may break the REST contract and must say so.
- A release is an annotated `vX.Y.Z` tag on a commit whose `main` pipeline run passed. The tag pipeline promotes that run's `sha-<commit>` image to the release tag, cuts the GitHub release, and publishes the skill, the plugin and the MCP Registry entry.
