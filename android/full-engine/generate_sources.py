"""Run only reviewed Python source generators from Ninja's topological commands.

The upstream graph gives certain generated files an order-only dependency on the
whole Windows object library. Building those outputs normally also tries to build
that library. This driver does not delete dependencies: it extracts the ordered
commands and executes only the reviewed source-generation tools. No compiler or
linker command is run, no source generator is replaced, and missing outputs remain
failures. LINK-ONLY still requires the upstream explicit double opt-in. The two
real-ROM verification/recipe steps are explicitly NOT RUN, including their stamp.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

TOOLS = {'hostgen.py', 'ovdata.py', 'romdata.py', 'romblob.py',
         'romblob_verify.py', 'romblob_recipe.py'}


def parse_generator(line: str, build: Path, root: Path) -> list[list[str]]:
    tokens = shlex.split(line)
    if not tokens or tokens[0] != 'cd':
        return []  # Native compilation is performed separately, never here.
    if len(tokens) < 6 or tokens[2] != '&&' or Path(tokens[1]).resolve() != build.resolve():
        raise ValueError('Unreviewed custom-command prefix: ' + line[:200])
    commands, current = [], []
    for token in tokens[3:] + ['&&']:
        if token == '&&':
            if not current:
                raise ValueError('Empty command segment')
            commands.append(current)
            current = []
        elif token in (';', '|', '||', '>', '>>', '<', '&'):
            raise ValueError('Unsupported shell operator in generator')
        else:
            current.append(token)
    checked = []
    for cmd in commands:
        exe = Path(cmd[0]).name
        if exe in ('python', 'python3') and len(cmd) > 1:
            script = Path(cmd[1]).resolve()
            if script.parent != (root / 'port/tools').resolve() or script.name not in TOOLS:
                raise ValueError('Unreviewed source generator: ' + str(script))
            checked.append([sys.executable, str(script), *cmd[2:]])
        elif exe == 'cmake' and len(cmd) == 4 and cmd[1:3] == ['-E', 'touch']:
            target = Path(cmd[3]).resolve()
            if not target.is_relative_to(build.resolve()):
                raise ValueError('Stamp path escapes build directory')
            checked.append(cmd)
        else:
            raise ValueError('Unreviewed custom command: ' + ' '.join(cmd)[:200])
    if not checked or Path(checked[0][0]).name.startswith('cmake'):
        raise ValueError('Custom command does not begin with a reviewed generator')
    return checked


def generate(build: Path, paths: list[str], output: Path) -> int:
    root = Path(__file__).resolve().parents[2]
    output.mkdir(parents=True, exist_ok=True)
    if not paths:
        (output / 'generators.log').write_text('All generated source outputs already exist.\n')
        return 0
    # Ninja computes the dependency order; -t commands never performs the build.
    plan = subprocess.run(['ninja', '-C', str(build), '-t', 'commands', *paths],
                          capture_output=True, text=True, timeout=45)
    if plan.returncode:
        (output / 'generators.log').write_text(plan.stdout + plan.stderr)
        return plan.returncode
    records, skipped, resource_checks = [], 0, []
    with (output / 'generators.log').open('w') as log:
        for line in plan.stdout.splitlines():
            try:
                commands = parse_generator(line, build, root)
            except ValueError as exc:
                records.append({'command': line, 'error': str(exc), 'returncode': 1})
                log.write(str(exc) + '\n')
                continue
            if not commands:
                skipped += 1
                continue
            if Path(commands[0][1]).name in ('romblob_verify.py', 'romblob_recipe.py'):
                # These consume real cartridge bytes and do not produce C/C++.
                # Do not execute their success stamp or imply resource validity.
                resource_checks.append({'commands': commands,
                                        'status': 'NOT RUN: requires real extracted ROM'})
                log.write('NOT RUN (requires real ROM): ' + line + '\n')
                continue
            for cmd in commands:
                log.write('$ ' + shlex.join(cmd) + '\n')
                log.flush()
                try:
                    rc = subprocess.run(cmd, cwd=build, stdout=log, stderr=subprocess.STDOUT,
                                        env={**os.environ, 'SM64DS_LINK_ONLY': '1'}, timeout=45).returncode
                except subprocess.TimeoutExpired:
                    rc = 124
                records.append({'command': cmd, 'returncode': rc})
                if rc: break  # Preserve the original && semantics.
    missing = [p for p in paths if not Path(p).is_file()]
    report = {'executed': len(records), 'skipped_compile_commands': skipped,
              'failed': sum(r['returncode'] != 0 for r in records),
              'missing_outputs': missing, 'skipped_resource_checks': resource_checks, 'commands': records}
    (output / 'generators.json').write_text(json.dumps(report, indent=2))
    print(f"Generators: {report['executed']} commands, {report['failed']} failures, "
          f"{len(missing)} missing outputs; {len(resource_checks)} real-ROM checks NOT RUN; "
          "no compiler invoked in this phase", flush=True)
    return 1 if report['failed'] or missing else 0
