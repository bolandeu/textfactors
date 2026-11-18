# Changelog

## [Unreleased]

- Replace the demo with text and HTML measurement, metric corridors, pairwise
  comparison, and comparison against a set, in Python and the generated CLI.
- Accept `--file PATH` or `--file -` for text and HTML measurements, and
  JSON or JSONL on stdin for all operations in `--json` mode.
- Drop reviews widgets, cookie banners, related posts, share bars and contact
  panels from HTML measurement; a CAPTCHA widget no longer marks a full page as
  blocked.
- Add `check_keywords` / `textfactors run check-keywords`: exact, lemma,
  diluted, reverse and any-word occurrence counts with density and optional targets.
- Add `check_html_keywords` / `textfactors run check-html-keywords`: same checks
  on a cleaned page zone, with `--file` support.
- Count headings from H1 to H6 in `structure`; report `stop_words` with counts
  and densities for text water.
- Add a `page` block with the full visible page text, so volume can be compared
  with external services without changing the service-text blocks.

## [0.1.0]

- Initial Python API and generated CLI.
