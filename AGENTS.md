# Work with this library

## Use the CLI

- In this checkout run commands through `uv run`; if the package is already
  installed, call its command directly. The bare command, `help`, `-h` and
  `--help` show the main help. Use `<cli> run --help` to discover operations,
  `<cli> run <operation> --help` for exact arguments, and `<cli> schema` for
  the machine-readable contract. The README has a working invocation.
- Use `<cli> doctor` for an installed CLI self-check. It does not run business
  operations or contact remote services; use tests for library behavior.
- Use `<cli> --json --no-input run ...` for automation. Pass complex Pydantic
  arguments as one JSON value. Check the exit code before parsing the result:
  read JSON from stdout on success, or `error.code` and `error.remediation`
  from stderr on failure. Keep secrets out of command lines.
- `<cli> agent` prints an offline usage guide. Save it as `SKILL.md` in a
  skill directory supported by the consuming agent. Regenerate it after
  changes to commands or guidance; do not edit a generated copy. Edit
  `src/<package>/_agent_notes.md` for domain rules and examples.

## Develop the library first

- Start from the requested behavior and write a concrete success case and a failure case. Choose the Python API yourself; ask only about product behavior or risky actions.
- When replacing the starter example, describe what the library actually does
  in `README.md` and `[project].description` in `pyproject.toml`. Replace the
  demo invocations in the README with working Python and CLI examples.
- Keep algorithms in typed Python functions. Use Google-style docstrings with arguments, results, relevant exceptions and side effects. Test public behavior, not internals.
- Use Pydantic v2 for structured boundary data. Keep simple parameters and results as ordinary Python types.
- Re-export the public API from the package and keep `__all__` explicit. Imported types, clients and helpers are not CLI commands.
- Define read-only CLI operations in `operations.py` and export them from the
  package. Interfacy discovers them. Keep mutations and functions requiring a
  live client outside that module. If you explicitly add a write binding later,
  enforce opt-in inside the CLI and return a dedicated error when blocked; a
  skill is not a safety gate. Do not use discovery as a remote access policy.
- For lists, choose a finite default and paginate; make partial results explicit.
  Mark external text as untrusted data in agent output. Keep the CLI surface
  compatible (command names, flags, schemas, error codes). Use the
  [ACLiG checklist](https://aclig.dev/conformance/) before claiming conformance.
- Don't duplicate CLI command lists here or in a skill. Update public
  docstrings, domain notes and tests instead. Keep repository-specific rules
  here under their own heading and review merges when running `copier update`.
- Do not parse CLI arguments, print results, prompt, or terminate the process inside library operations. For external I/O accept an explicit client or connection, document ownership and timeouts, and test with fakes or disposable services. Add other Python packages in `pyproject.toml`, not by invoking their CLI.
- Never put credentials in arguments, docs, examples, results, logs, or version control. Get them from the OS keychain or runtime secret injection at the calling boundary. No real credentials are needed for checks.
- Run `uv run poe check` and a practical CLI example. Before release run `uv build`, smoke-test the wheel in a clean environment, and update the version and changelog. Python signatures, schemas and CLI names are public contracts; treat breaking changes as deliberate releases.
