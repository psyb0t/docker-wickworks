# Docs and releases

- The documentation pages are `docs/`, built by the Docusaurus site in `website/` and published to GitHub Pages from `main` by `.github/workflows/docs.yml` at https://psyb0t.github.io/docker-wickworks/.
- Keep `docs/` flat. Every page needs `title` and `description` front matter; a new page goes into `website/sidebars.mjs` and `website/static/llms.txt`.
- After a docs change, run `make docs`; it fails on a broken link or anchor. After a dependency change in `website/package.json`, run `make docs-lock` first.
- A behavior, setting, endpoint or indicator change updates the matching docs page, `schema.json`, `metadata.py`, the skill and the plugin README in the same change.
- CHANGELOG entries use the `## vX.Y.Z (YYYY-MM-DD)` heading. Pre-1.0, a minor bump may break the REST contract and must say so.
- A release is an annotated `vX.Y.Z` tag on a commit whose `main` pipeline run passed. The tag pipeline promotes that run's `sha-<commit>` image to the release tag, cuts the GitHub release, and publishes the skill, the plugin and the MCP Registry entry.
