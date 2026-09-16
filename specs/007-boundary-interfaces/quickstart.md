# Quickstart — verifying the boundary interfaces

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) |
**Contracts**: [interfaces.md](./contracts/interfaces.md),
[errors.md](./contracts/errors.md), [contract-suites.md](./contracts/contract-suites.md)

How a reviewer checks this feature without taking anything on trust. Nothing here needs a network,
a Hindsight instance, a database or a fixture file (NFR-003).

## Prerequisites

```bash
uv sync
```

## 1. The whole suite is green

```bash
uv run pytest -q
```

The branch point was `677 passed`; this feature adds to that and removes nothing.

## 2. The six contract suites pass against the six fakes (SC-002)

```bash
uv run pytest tests/contracts -q
```

Every fake is an in-memory implementation that performs no I/O, and each is run against the suite
belonging to its boundary — the first proof each interface is implementable by something other than
the eventual real thing.

## 3. Each suite is watched failing (SC-003)

```bash
uv run pytest tests/contracts/test_suites_bite.py -v
```

Six tests, one per boundary, each holding a deliberately broken implementation against its suite and
asserting the suite rejects it — the archive that drops timestamps, the memory store that appends
instead of replacing, the import state that forgets failures. Read the table in
[contract-suites.md](./contracts/contract-suites.md#every-suite-is-shown-to-fail-fr-020-sc-003) and
check each breakage is answered by the rule it should break.

A suite nobody has seen fail is a suite nobody knows is asserting anything.

## 4. The pipeline runs end to end with no I/O (SC-004, SC-005)

```bash
uv run pytest tests/integration/test_pipeline_from_fakes.py -v
```

`PL-5` is the one to read rather than skim: the network and filesystem are *blocked* for the
duration, not merely unobserved. The guard covers `socket.socket`, `builtins.open`, `Path.open`,
`Path.write_text` and `Path.write_bytes`. It does not cover `os.open` or a C extension reaching the
filesystem directly — it is there to catch the realistic mistake, a fake that quietly writes a temp
file, not to sandbox a hostile implementation (research R14).

## 5. The memory engine is replaceable (SC-006)

```bash
uv run pytest tests/integration/test_pipeline_from_fakes.py -k replaceable -v
```

The same pipeline with a second, differently-implemented memory store fake. If this needs more than
the composition line to change, ADR-001's exit strategy is not real and the interface is wrong.

## 6. Hindsight is nowhere (SC-007)

```bash
uv run pytest tests/structure -q
```

Two checks matter here:

* the boundary guard over the interface modules — no Hindsight, no HTTP client, no storage library
  in the transitive import graph;
* the vocabulary check — no public name in any interface is a Hindsight term.

Then confirm the guard bites, the same way #8's does:

```bash
uv run pytest tests/structure/test_module_layout.py -k "bites or sibling" -v
```

This feature fills five boundaries, and narrowing `FILLED_BOUNDARIES` by dotted prefix is what keeps
`memory/hindsight` guarded while `memory/interface` is filled (research R15). One of these tests
exists specifically for that sibling case — code placed in `memory/hindsight/` must still be caught.

## 7. Read the interfaces against §8

Open [interfaces.md](./contracts/interfaces.md) beside ARCHITECTURE.md §8 and check the mapping is
one to one: six rows, six protocols, one responsibility each, nothing merged and nothing split
(SC-001).

Then check what is absent, which is the part a reading can miss: no export is parsed, no redaction
pattern is written, no alias rule is matched, no file is stored, no database is opened and no
Hindsight call is made (SC-010, FR-027). Those are #10 through #16.

## 8. Lint

```bash
uv run ruff check .
uv run ruff format --check .
```
