#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Disassemble MicroPython .mpy bytecode files from the badge firmware dump.

Wraps the official MicroPython mpy-tool.py with a friendlier CLI supporting
single-file disassembly, hex dumps, header inspection, and batch processing.
"""

import argparse
import subprocess
import sys
from pathlib import Path

MPY_TOOL = Path(__file__).resolve().parent / "vendor" / "mpy-tool.py"


def run_mpy_tool(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(MPY_TOOL)] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def cmd_disasm(args: argparse.Namespace) -> int:
    flags = ["-d"]
    if args.json:
        flags.append("-j")
    for f in args.files:
        proc = run_mpy_tool(flags + [str(f)])
        if args.output:
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(proc.stdout, encoding="utf-8")
        else:
            sys.stdout.write(proc.stdout)
        if proc.returncode != 0:
            return proc.returncode
    return 0


def cmd_hexdump(args: argparse.Namespace) -> int:
    for f in args.files:
        proc = run_mpy_tool(["-x", str(f)])
        if args.output:
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(proc.stdout, encoding="utf-8")
        else:
            sys.stdout.write(proc.stdout)
        if proc.returncode != 0:
            return proc.returncode
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    for f in args.files:
        proc = run_mpy_tool(["-d", str(f)])
        if proc.returncode != 0:
            sys.stderr.write(f"error: {f}: {proc.stdout}\n")
            return proc.returncode
        lines = []
        for line in proc.stdout.splitlines():
            lines.append(line)
            if line.strip() == "" and lines:
                break
        output = "\n".join(lines) + "\n"
        if args.output:
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(output, encoding="utf-8")
        else:
            sys.stdout.write(output)
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    root = Path(args.files[0])
    if not root.is_dir():
        sys.stderr.write(f"error: {root} is not a directory\n")
        return 1

    out_dir = Path(args.output) if args.output else Path("disassembly")
    out_dir.mkdir(parents=True, exist_ok=True)

    flags = ["-d"]
    if args.json:
        flags.append("-j")

    mpy_files = sorted(root.rglob("*.mpy"))
    if not mpy_files:
        sys.stderr.write(f"error: no .mpy files found in {root}\n")
        return 1

    failures = []
    for src in mpy_files:
        rel = src.relative_to(root)
        dst = out_dir / rel.with_suffix(".dis.txt")
        dst.parent.mkdir(parents=True, exist_ok=True)

        proc = run_mpy_tool(flags + [str(src)])
        dst.write_text(proc.stdout, encoding="utf-8")

        status = "OK" if proc.returncode == 0 else "FAIL"
        print(f"  {status}  {rel}")
        if proc.returncode != 0:
            failures.append(str(rel))

    summary_lines = [
        f"root: {root}",
        f"total_mpy: {len(mpy_files)}",
        f"passed: {len(mpy_files) - len(failures)}",
        f"failures: {len(failures)}",
    ]
    if failures:
        summary_lines.append("failed:")
        summary_lines.extend(f"  {f}" for f in failures)
    else:
        summary_lines.append("failed: none")

    summary = out_dir / "SUMMARY.txt"
    summary.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print()
    print(summary.read_text(encoding="utf-8"))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="mpy_disasm",
        description="Disassemble MicroPython .mpy bytecode files.",
        epilog="""\
examples:
  uv run tools/mpy_disasm.py dump/config.mpy
  uv run tools/mpy_disasm.py hexdump dump/config.mpy
  uv run tools/mpy_disasm.py batch dump/
  uv run tools/mpy_disasm.py batch dump/ -o analysis/disassembly
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    sub = parser.add_subparsers(dest="command")

    # -- disasm (default) --
    p_dis = sub.add_parser("disasm", help="disassemble bytecode (default)")
    p_dis.add_argument("files", nargs="+", help=".mpy file(s) to disassemble")
    p_dis.add_argument("-o", "--output", help="output file (default: stdout)")
    p_dis.add_argument("-j", "--json", action="store_true", help="JSON output")

    # -- hexdump --
    p_hex = sub.add_parser("hexdump", help="annotated hex dump")
    p_hex.add_argument("files", nargs="+", help=".mpy file(s) to hex-dump")
    p_hex.add_argument("-o", "--output", help="output file (default: stdout)")

    # -- info --
    p_info = sub.add_parser("info", help="header and qstr table only")
    p_info.add_argument("files", nargs="+", help=".mpy file(s) to inspect")
    p_info.add_argument("-o", "--output", help="output file (default: stdout)")

    # -- batch --
    p_batch = sub.add_parser("batch", help="batch-process a directory tree")
    p_batch.add_argument("files", nargs=1, help="directory containing .mpy files")
    p_batch.add_argument("-o", "--output", help="output directory (default: disassembly/)")
    p_batch.add_argument("-j", "--json", action="store_true", help="JSON output")

    if not MPY_TOOL.exists():
        sys.stderr.write(f"error: vendored mpy-tool not found at {MPY_TOOL}\n")
        return 1

    # Default to disasm when no subcommand is given
    subcommands = {"disasm", "hexdump", "info", "batch"}
    argv = sys.argv[1:]
    if argv and argv[0] not in subcommands and not argv[0].startswith("-"):
        argv = ["disasm"] + argv
    elif not argv:
        parser.print_help()
        return 0

    args = parser.parse_args(argv)

    dispatch = {
        "disasm": cmd_disasm,
        "hexdump": cmd_hexdump,
        "info": cmd_info,
        "batch": cmd_batch,
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
