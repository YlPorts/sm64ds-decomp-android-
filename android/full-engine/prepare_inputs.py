"""Reuse reviewed stage-0.2/0.3/0.4 adapters in the full-source NDK attempt."""
from __future__ import annotations
from copy import deepcopy
import importlib.util
from pathlib import Path


def load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(units: list[dict], output: Path) -> list[dict]:
    root = Path(__file__).resolve().parents[2]
    ntr = load(root / 'android/engine/tools/adapt_ntr.py')
    runtime = load(root / 'android/native/tools/adapt_runtime.py')
    scheduler = load(root / 'android/native/tools/adapt_scheduler.py')
    mapping = {}
    for name in ('io', 'runtime', 'backup', 'rt'):
        source = root / 'port/ntr' / (name + '.cpp')
        target = output / 'adapted/ntr' / (name + '.cpp')
        if name == 'rt':
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(runtime.adapt(source.read_text()))
        else:
            ntr.generate(source, target)
        mapping[str(source.resolve())] = str(target.resolve())
    source = root / 'port/hal/boot2_thread.cpp'
    target = output / 'adapted/hal/boot2_thread.cpp'
    scheduler.adapt(source, target)
    mapping[str(source.resolve())] = str(target.resolve())
    result = []
    for unit in units:
        if unit['source'] not in mapping:
            result.append(unit)
            continue
        item = deepcopy(unit)
        item['original_source'] = item['source']
        item['source'] = mapping[item['source']]
        item['generated'] = True
        item['adaptation'] = 'reused reviewed native adapter; no upstream source edit'
        group = item['group']
        group.setdefault('defines', []).append({'define':'SM64DS_NATIVE_FIBERS=1'})
        for inc in ('android/native/include', 'android/engine/include', 'port', 'port/hal', 'port/ntr'):
            group.setdefault('includes', []).append({'path':str(root / inc)})
        result.append(item)
    return result
