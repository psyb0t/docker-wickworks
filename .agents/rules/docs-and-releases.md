# Docs and releases

- The documentation site is `docs/`, published by GitHub Pages from `main` at https://psyb0t.github.io/docker-wickworks/ with the Just the Docs theme (`remote_theme` pinned in `docs/_config.yml`, colors in `docs/_sass/`).
- Keep `docs/` flat.
- Wrap code blocks containing `{{` or `{%` in `<!-- {% raw %} -->` and `<!-- {% endraw %} -->`, or Jekyll renders them empty.
- After a docs change, run `make docs` and check the output in `.testing/docs-site` before handing off.
- A behavior, setting, endpoint or indicator change updates the matching docs page, `schema.json`, `metadata.py`, the skill and the plugin README in the same change.
- CHANGELOG entries use the `## vX.Y.Z (YYYY-MM-DD)` heading. Pre-1.0, a minor bump may break the REST contract and must say so.
- A release is an annotated `vX.Y.Z` tag on a commit whose `main` pipeline run passed. The tag pipeline promotes that run's `sha-<commit>` image to the release tag, cuts the GitHub release, and publishes the skill, the plugin and the MCP Registry entry.
