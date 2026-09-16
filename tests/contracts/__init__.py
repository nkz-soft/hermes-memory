"""The contract suites: the tests that define what implementing a boundary of §8 means.

A suite here belongs to the **boundary**, not to any implementation of it. An implementation is
run against one by subclassing it and supplying itself through the suite's factory method, so
passing the suite is what "implements this boundary" means rather than "does not crash"
(specs/007-boundary-interfaces/contracts/contract-suites.md, research.md R11).

Nothing in a suite may name a file, a URL, a table, a fixture or an implementation: #13's archive
on local storage and a later one on object storage are held to the same rules, or the rules were
never about the boundary.
"""
