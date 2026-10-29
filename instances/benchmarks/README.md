# SMT-LIB benchmarks

These benchmarks are selected from the [SMT-LIB 2025 non-incremental release](https://zenodo.org/records/16740866)
(version 2025.08.04). Their contents are unchanged; the original contributor and
source metadata remain in each file.

## License and attribution

These third-party benchmarks are separate from Interval Finder's MIT-licensed
source code. The upstream release distributes benchmarks under the
[Creative Commons Attribution 4.0 International license](https://creativecommons.org/licenses/by/4.0/),
unless a benchmark specifies otherwise. See the
[upstream release README](https://zenodo.org/records/16740866/files/README.md?download=1)
and any license information in the individual files. Preserve this attribution
and the original metadata when redistributing these files.

The release is curated by Mathias Preiner, Hans-Jörg Schurr, Clark Barrett,
Pascal Fontaine, Aina Niemetz, and Cesare Tinelli. Individual benchmark authors
and contributors retain their respective rights.

## Selected families

| Directory | Upstream families |
|---|---|
| `QF_LIA` | `nec-smt/small/checkpass_pwd`, `nec-smt/small/config_read_line`, `calypto` |
| `QF_LRA` | `sal/windowreal`, `check`, `meti-tarski/atan`, `meti-tarski/sqrt`, `sc` |
| `QF_BV` | `sage/app7`, `bench_ab` |

The collection is a small demonstration sample, not a representative performance
suite. Each selected file has a verified disjoint domain for at least one variable.
