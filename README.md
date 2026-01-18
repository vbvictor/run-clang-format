# run-clang-format

[![PyPI](https://img.shields.io/pypi/v/run-clang-format)](https://pypi.org/project/run-clang-format/)
[![Code Lint](https://github.com/vbvictor/run-clang-format/actions/workflows/code-lint.yaml/badge.svg)](https://github.com/vbvictor/run-clang-format/actions/workflows/code-lint.yaml)
[![Code Format](https://github.com/vbvictor/run-clang-format/actions/workflows/code-format.yaml/badge.svg)](https://github.com/vbvictor/run-clang-format/actions/workflows/code-format.yaml)
[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/vbvictor/run-clang-format/blob/main/LICENSE)

Run clang-format in parallel over entire directory trees.

```bash
run-clang-format src/
```

Use `-i` flag to apply formatting in-place instead of showing diffs.

## Getting Started

Install from PyPI via `pip` or `pipx`:

```bash
pip install run-clang-format
```

## Usage

Check formatting and show diffs:

```bash
run-clang-format src/
```

Apply formatting in-place:

```bash
run-clang-format -i src/
```

Control parallelism (default uses all CPU cores):

```bash
run-clang-format -j 4 src/
```

## License

[Apache License 2.0](LICENSE)
