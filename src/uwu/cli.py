import argparse
import importlib.resources
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_LASTNAME = "carrico"
DEFAULT_IMAGE = "texbuilder:0.1.0"
CLEAN_PATTERNS = ("*.aux", "*.log", "*.out", "*.pdf")

EXAMPLE_BLOCK_RE = re.compile(r"\n?%%%% EXAMPLE %%%%.*?%%%% END EXAMPLE %%%%\n?", re.DOTALL)
PROBLEM_TOKEN_RE = re.compile(r"^(?P<num>\d+(?:\.\d+)*)(?:(?P<start>[a-zA-Z])(?:-(?P<end>[a-zA-Z]))?)?$")


def cmd_new(args: argparse.Namespace) -> int:
    path_arg = args.path.strip("/")
    dest_dir = Path(path_arg)
    base_name = args.output or f"{DEFAULT_LASTNAME}_{path_arg.replace('/', '_')}"

    if dest_dir.exists():
        print(f"error: {dest_dir} already exists", file=sys.stderr)
        return 1

    dest_dir.mkdir(parents=True)
    template = importlib.resources.files("uwu.data").joinpath("template.tex")
    tex_path = dest_dir / f"{base_name}.tex"
    tex_path.write_bytes(template.read_bytes())

    if args.problems:
        try:
            count = _insert_problems(tex_path, " ".join(args.problems))
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"created {tex_path} with {count} problem(s)")
    else:
        print(f"created {tex_path}")
    return 0


def _find_tex_file(target: Path) -> Path:
    if target.is_file():
        return target
    if not target.is_dir():
        raise FileNotFoundError(f"{target} does not exist")
    tex_files = sorted(target.glob("*.tex"))
    if not tex_files:
        raise FileNotFoundError(f"no .tex file found in {target}")
    if len(tex_files) > 1:
        names = ", ".join(f.name for f in tex_files)
        raise ValueError(f"multiple .tex files in {target} ({names}); pass one explicitly")
    return tex_files[0]


def cmd_build(args: argparse.Namespace) -> int:
    try:
        tex_file = _find_tex_file(Path(args.path))
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    work_dir = tex_file.parent.resolve()
    jobname = args.output or tex_file.stem

    for pattern in CLEAN_PATTERNS:
        for stale in work_dir.glob(pattern):
            stale.unlink()

    cmd = [
        "docker", "run",
        "-u", f"{os.getuid()}:{os.getgid()}",
        "-v", f"{work_dir}:/project",
        args.image,
        "pdflatex", "-interaction=nonstopmode",
        "-jobname", jobname,
        tex_file.name,
    ]
    result = subprocess.run(cmd, cwd=work_dir)
    if result.returncode == 0:
        print(f"built {work_dir / (jobname + '.pdf')}")
    return result.returncode


def _parse_problems(spec: str) -> dict[str, list[str]]:
    problems: dict[str, list[str]] = {}
    for raw in spec.split(","):
        token = raw.strip()
        if not token:
            continue
        match = PROBLEM_TOKEN_RE.match(token)
        if not match:
            raise ValueError(f"can't parse problem {token!r}")
        start, end = match["start"], match["end"]
        if start is None:
            letters = []
        elif end is None:
            letters = [start]
        else:
            if start > end:
                raise ValueError(f"bad range {token!r}")
            letters = [chr(code) for code in range(ord(start), ord(end) + 1)]
        problems.setdefault(match["num"], []).extend(letters)
    return problems


def _render_problems(problems: dict[str, list[str]]) -> str:
    blocks = []
    for num, letters in problems.items():
        lines = [f"\\problem{{{num}}}{{}}"]
        if not letters:
            lines += ["", "\\solution{", "", "}"]
        else:
            for letter in letters:
                lines += ["", f"\\subproblem{{{letter}.}}{{}}", "\\solution{", "", "}"]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _insert_problems(tex_file: Path, spec: str) -> int:
    problems = _parse_problems(spec)
    if not problems:
        raise ValueError("no problems given")

    text = tex_file.read_text()
    marker = "\\end{document}"
    if marker not in text:
        raise ValueError(f"{tex_file} has no \\end{{document}}")

    text = EXAMPLE_BLOCK_RE.sub("\n", text, count=1)
    text = text.replace(marker, f"{_render_problems(problems)}\n\n{marker}", 1)
    tex_file.write_text(text)
    return len(problems)


def cmd_problems(args: argparse.Namespace) -> int:
    try:
        tex_file = _find_tex_file(Path(args.path))
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    try:
        count = _insert_problems(tex_file, " ".join(args.problems))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"inserted {count} problem(s) into {tex_file}")
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="uwu", description="Scaffold and build LaTeX homework assignments")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser("new", help="copy the template into a new assignment directory")
    new_parser.add_argument("path", help="assignment path to create, e.g. spce5085/a1")
    new_parser.add_argument("-o", "--output", help="override the generated .tex base filename")
    new_parser.add_argument(
        "problems", nargs="*", help='optional problem list, e.g. 4.1, 4.2, 4.4a, 4.8a-b, 4.11i'
    )
    new_parser.set_defaults(func=cmd_new)

    build_parser = subparsers.add_parser("build", help="build a homework .tex file with pdflatex via docker")
    build_parser.add_argument("path", nargs="?", default=".", help="assignment directory or .tex file (default: .)")
    build_parser.add_argument("-o", "--output", help="output PDF/job name (default: .tex filename)")
    build_parser.add_argument("--image", default=DEFAULT_IMAGE, help=f"docker image to build with (default: {DEFAULT_IMAGE})")
    build_parser.set_defaults(func=cmd_build)

    problems_parser = subparsers.add_parser(
        "problems", help="insert \\problem/\\subproblem/\\solution skeletons for a list of problems"
    )
    problems_parser.add_argument("path", help="assignment directory or .tex file")
    problems_parser.add_argument(
        "problems", nargs="+", help='problem list, e.g. "4.1, 4.2, 4.4a, 4.8a-b, 4.11i"'
    )
    problems_parser.set_defaults(func=cmd_problems)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
