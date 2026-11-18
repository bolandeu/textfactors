# rb-textfactors

An offline Python library and CLI for measuring text and HTML, summarizing
metrics across pages, and comparing results against one page or a set.

Installable package: `rb-textfactors`. Python import:
`rb_textfactors`. Shell command: `textfactors`.

## Run locally

```sh
uv sync --locked
uv run textfactors run --help
uv run textfactors --json --no-input run measure-text 'Доставка грузов из Китая' --top-n 1
uv run textfactors --json --no-input run measure-html '<h1>Delivery</h1><p>Cargo arrives by sea.</p>'
uv run textfactors --json --no-input run compare '{"blocks":{"text":{"words_count":5}}}' '{"blocks":{"text":{"words_count":800}}}' --blocks text
```

Use `textfactors` without `uv run` after installation. Install dependencies
from the configured Gitea index for `rb-semkit` and its `rb-dataio` dependency;
if installing a wheel outside this checkout, include that index with `--index`.
The tool measures supplied content. It does not fetch URLs or execute HTML
scripts.

Interfacy generates commands from the exports in `operations.py`. Use
`run <operation> --help` for exact syntax. Pass each measured result as one
quoted JSON object; for a list of results, pass several objects as separate
arguments, not a JSON array. List options also take one argument per item
(e.g. `--blocks text title`). Omit `--ignore-words` to use the default list;
pass it with no values to use an empty list.

### Files and pipelines

For `measure-text` and `measure-html`, use `--file PATH` instead of the
positional content argument. Files must be UTF-8. `--file -` reads raw content
from stdin, even when `--json` is set.

```sh
uv run textfactors --json --no-input run measure-html --file /absolute/path/to/page.html --top-n 3
printf '%s\n' 'Доставка грузов из Китая' | uv run textfactors run measure-text --file -
```

With global `--json` and **no arguments after the operation name**, all five
operations accept a JSON object on stdin. Use Python parameter names such as
`top_n`, and pass lists as JSON arrays. See `stdin_schema` for each operation
in `textfactors schema`. JSONL is also accepted: send one object per line and
receive one result per nonblank line, in input order. A single object can
span multiple lines.

```sh
printf '%s\n' '{"text":"Доставка грузов из Китая","top_n":1}' |
  uv run textfactors --json --no-input run measure-text
jq -c '. + {top_n: 3}' /absolute/path/to/spider.jsonl |
  uv run textfactors --json --no-input run measure-html
jq -nc --slurpfile a /absolute/path/to/a.json --slurpfile b /absolute/path/to/b.json '{a: $a[0], b: $b[0]}' |
  uv run textfactors --json --no-input run compare
```

`measure-html` accepts Spider fetch JSONL directly if each row carries `html`.
It ignores metadata fields; check HTTP status before using a page as a reference.
The `jq` step above only sets `top_n` to keep the output small. When using
`--file` or positional input, pass this setting as `--top-n` instead. It limits
repeat tables without changing metrics or densities.

Operations write JSON to stdout and failures to stderr with `error.code`,
`error.message` and `error.remediation`. Check the exit code before consuming
results. JSONL stops on the first failure; earlier result lines remain.
Exit codes: 0 success, 1 operation failure, 2 invalid arguments, 9 result
exceeds 64 KiB per record, 10 installed CLI check failed, and 130 interruption.

`doctor` prints a JSON report of local checks: command tree, schema and agent
usage guide. It works on an installed wheel without a checkout, network or
business operation calls. A failed check reports `error.check` on stderr.
It is not a test of business logic or external accounts.

## Discover commands and generate an agent skill

```sh
uv run textfactors schema
uv run textfactors agent > /absolute/path/to/skills/textfactors/SKILL.md
```

Create the destination skill directory first. You can run `textfactors agent`
from the installed wheel without `uv run`, a checkout or a network connection.
`agent` builds a portable `SKILL.md` from the same command tree as `--help`.
Change domain guidance and examples in `src/rb_textfactors/_agent_notes.md`;
regenerate exported skills instead of editing their command lists by hand.
`schema` provides the full command tree, arguments, Pydantic JSON schemas,
exit codes and the current safety state. `AGENTS.md` explains repository rules
and how to update them with Copier.

The [Agent CLI Guidelines](https://aclig.dev/conformance/) are a release
checklist, not a conformance claim. If you add external content, mark it as
untrusted. If you add a write operation, gate it explicitly at the CLI boundary.

## Import from Python

```python
from rb_textfactors import average, compare, compare_with_set, measure_html, measure_text

text = measure_text("доставка грузов из Китая")
assert text["words_count"] == 3
own = {"blocks": {"text": text}}
page = measure_html("<h1>Доставка</h1><p>Морская доставка грузов. Оформляем документы.</p>")

corridor = average([own, page], blocks=["text"])
pair = compare(own, page, blocks=["text"])
against_set = compare_with_set(own, [page], share=0.6, blocks=["text"])
```

`measure_text` returns one block of 12 metrics, norms and repeat tables. Wrap
it under `blocks.text` for comparisons. `measure_html` already returns a
`blocks` mapping, along with `structure` and `quality`. A quality rejection
still returns the blocks. `average` uses nearest-rank quartiles. A set
comparison computes its corridor from the reference items alone and reads
missing keys from the `text` and `text_links` repeat tables; use full repeat
tables for this analysis (`top_n=0`).

Before counting, `measure_html` drops page chrome: scripts, styles, navigation,
footer, aside, forms, reviews widgets (`.rb-reviews`, Trustindex, WP Google
Reviews), cookie banners, related-post blocks, share buttons, sitemap widgets
and `[hidden]`/`[aria-hidden]` nodes. A contact panel with a form and a
"Свяжитесь с нами" heading is dropped whole, so its heading is not counted as
content. Pass already-clean article HTML if you need the full page text.

The five Python signatures and result keys follow `rb_textmetrics`; this
package does not import it. Text processing uses the same Semkit library as
the reference. A null `blocks` map is treated like an absent map, including
inside a mixed reference set. Malformed block shapes, invalid repeat key,
count or density values, and non-finite metrics raise `ValueError` instead
of leaking internal exceptions or returning values unsupported by JSON.

## Check keywords

`check_keywords` counts given phrases in a text and compares them with
targets. It works offline and does not call the Миратекст API.

```python
from rb_textfactors import check_keywords, measure_html

text = measure_html(html)["blocks"]["text"]
report = check_keywords(text, ["таможенный представитель", "вэд"], targets=[3, 2])
assert report["words_total"] == text["words_total"]
for row in report["keywords"]:
    print(row["keyword"], row["find"], row["density"], row["met"])
```

Match types are opt-in flags:

- `exact` (default) — phrase as written, case and `ё` ignored;
- `lemma` (default) — any grammatical form, words still adjacent;
- `diluted` — up to `window` other words between phrase words, order kept;
- `reverse` — phrase words in reverse order, gaps allowed.

Counts never overlap: each occurrence is classified by the first enabled rule
that matches. `density` is the found count per 100 words. Without `targets`,
`met` is `null` and only counts are reported.

## Build, document, and release

```sh
uv run poe check
uv run --group docs zensical build --strict
uv build
```

Commit `uv.lock` so CI can use `uv run --locked`. For each release, update the
package version in `pyproject.toml` and `CHANGELOG.md`, then build and check the
wheel. A pushed matching `vX.Y.Z` tag creates a GitHub release with both package
archives. To publish to a package index, explicitly run `uv publish` with the
index credentials supplied by a secret store (e.g. `UV_PUBLISH_TOKEN`). CI does
not publish to PyPI by default.

## Update from the starter

Keep `.copier-answers.yml` committed. Commit or stash your changes before
updating. When the starter publishes a new template tag, replace the path
below with the absolute path to this project and run:

```sh
uvx copier update --defaults /absolute/path/to/this-package
uv --directory /absolute/path/to/this-package sync
uv --directory /absolute/path/to/this-package run poe check
```

Review the resulting diff and resolve any merge conflicts before committing.
The answers file preserves the distribution and CLI names; changing the
folder name does not change either. The library version is independent of the
template version.

Template source and credits: [pawamoy/copier-uv](https://github.com/pawamoy/copier-uv),
ISC license.
