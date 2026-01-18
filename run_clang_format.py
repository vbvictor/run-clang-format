#!/usr/bin/env python3
#
# ===- run-clang-format.py - Parallel clang-format runner ----*- python -*--===#
#
# ===-----------------------------------------------------------------------===#

"""
Parallel clang-format runner
============================

Runs clang-format over all files in a directory tree.
Requires clang-format in $PATH.

Example invocations:
- Check formatting and show diffs:
    run-clang-format.py .

- Apply formatting in-place:
    run-clang-format.py -i .

- Format with specific style:
    run-clang-format.py -i --style=Google src/
"""

import argparse
import asyncio
import difflib
import multiprocessing
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, List, Optional, TypeVar


def find_binary(arg: str, name: str) -> str:
    """Get the path for a binary or exit"""
    if arg:
        if shutil.which(arg):
            return arg
        else:
            raise SystemExit(
                f"error: passed binary '{arg}' was not found or is not executable"
            )

    binary = shutil.which(name)
    if binary:
        return binary
    else:
        raise SystemExit(f"error: failed to find {name} in $PATH")


def get_format_invocation(
    filename: str,
    clang_format_binary: str,
    style: Optional[str],
    in_place: bool,
) -> List[str]:
    """Gets a command line for clang-format."""
    command = [clang_format_binary]
    if style:
        command.extend([f"--style={style}"])
    if in_place:
        command.append("-i")
    command.append(filename)
    return command


# FIXME Python 3.12: This can be simplified out with run_with_semaphore[T](...).
T = TypeVar("T")


async def run_with_semaphore(
    semaphore: asyncio.Semaphore,
    f: Callable[..., Awaitable[T]],
    *args: Any,
    **kwargs: Any,
) -> T:
    async with semaphore:
        return await f(*args, **kwargs)


@dataclass
class ClangFormatResult:
    filename: str
    invocation: List[str]
    returncode: int
    stdout: str
    stderr: str
    elapsed: float
    original_content: Optional[str] = None


async def run_clang_format(
    filename: str,
    clang_format_binary: str,
    style: Optional[str],
    in_place: bool,
) -> ClangFormatResult:
    """
    Runs clang-format on a single file and returns the result.
    """
    invocation = get_format_invocation(filename, clang_format_binary, style, in_place)

    original_content = None
    if not in_place:
        try:
            with open(filename, "r", encoding="utf-8") as f:
                original_content = f.read()
        except Exception:
            pass

    try:
        process = await asyncio.create_subprocess_exec(
            *invocation, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        start = time.time()
        stdout, stderr = await process.communicate()
        end = time.time()
    except asyncio.CancelledError:
        process.terminate()
        await process.wait()
        raise

    assert process.returncode is not None
    return ClangFormatResult(
        filename,
        invocation,
        process.returncode,
        stdout.decode("UTF-8"),
        stderr.decode("UTF-8"),
        end - start,
        original_content,
    )


def find_files(paths: List[str]) -> List[str]:
    """Find all files to be formatted."""
    extensions = {
        ".c",
        ".h",
        ".cpp",
        ".hpp",
        ".cc",
        ".hh",
        ".cxx",
        ".hxx",
        ".c++",
        ".h++",
        ".m",
        ".mm",
    }
    files = set()

    for path in paths:
        if os.path.isfile(path):
            files.add(os.path.abspath(path))
        elif os.path.isdir(path):
            for root, dirs, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(root, filename)
                    _, ext = os.path.splitext(filename)
                    if ext.lower() in extensions:
                        files.add(os.path.abspath(filepath))

    return sorted(files)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Runs clang-format over all files "
        "in a directory tree. Requires "
        "clang-format in $PATH."
    )

    parser.add_argument(
        "-i",
        action="store_true",
        default=False,
        help="Apply edits to files instead of displaying diffs",
    )

    parser.add_argument(
        "-clang-format-binary", metavar="PATH", help="Path to clang-format binary."
    )

    parser.add_argument(
        "-style",
        default=None,
        help="Formatting style to apply (LLVM, GNU, Google, Chromium, "
        "Microsoft, Mozilla, WebKit, file).",
    )

    parser.add_argument(
        "-j",
        type=int,
        default=0,
        help="Number of format instances to be run in parallel.",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Be more verbose, ineffective without -i",
    )

    parser.add_argument(
        "files", nargs="*", default=["."], help="Files or directories to be processed."
    )

    args = parser.parse_args()

    # Find clang-format binary
    clang_format_binary = find_binary(args.clang_format_binary, "clang-format")

    # Test clang-format
    try:
        subprocess.run(
            [clang_format_binary, "--version"], capture_output=True, check=True
        )
    except subprocess.CalledProcessError:
        print("Unable to run clang-format.", file=sys.stderr)
        sys.exit(1)

    # Find all files to process
    files = find_files(args.files)

    if not files:
        if args.verbose:
            print("No files found to format.")
        return

    if args.verbose:
        action = "Formatting" if args.i else "Checking"
        print(f"{action} {len(files)} files ...")

    # Determine number of workers
    max_task = args.j
    if max_task == 0:
        max_task = multiprocessing.cpu_count()

    returncode = 0
    has_diff = False
    semaphore = asyncio.Semaphore(max_task)
    tasks = [
        asyncio.create_task(
            run_with_semaphore(
                semaphore,
                run_clang_format,
                filename,
                clang_format_binary,
                args.style,
                args.i,
            )
        )
        for filename in files
    ]

    try:
        for i, coro in enumerate(asyncio.as_completed(tasks)):
            result = await coro

            if result.returncode != 0:
                returncode = 1
                if result.returncode < 0:
                    result.stderr += f"{result.filename}: terminated by signal {-result.returncode}\n"

            progress = f"[{i + 1: >{len(f'{len(files)}')}}/{len(files)}]"
            runtime = f"[{result.elapsed:.1f}s]"

            if args.i:
                # In-place mode
                if args.verbose:
                    print(f"{progress}{runtime} {' '.join(result.invocation)}")
                if result.stderr:
                    print(result.stderr, file=sys.stderr)
            else:
                # Diff mode
                if result.original_content and result.stdout != result.original_content:
                    has_diff = True
                    diff = difflib.unified_diff(
                        result.original_content.splitlines(keepends=True),
                        result.stdout.splitlines(keepends=True),
                        result.filename,
                        result.filename,
                        "(before formatting)",
                        "(after formatting)",
                    )
                    sys.stdout.write("".join(diff))

                if result.stderr:
                    print(result.stderr, file=sys.stderr)

    except asyncio.CancelledError:
        print("\nCtrl-C detected, goodbye.")
        for task in tasks:
            task.cancel()
        return

    # Return 1 if there were diffs (when not applying changes)
    if not args.i and has_diff:
        returncode = 1

    sys.exit(returncode)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
