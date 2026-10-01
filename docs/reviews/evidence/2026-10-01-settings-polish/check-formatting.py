"""Compare every formatting-only module's AST with the requested PR base."""
import ast
import subprocess
from pathlib import Path

MODULES = ('settings', 'settings_schema', 'settings_fields', 'settings_components', 'preferences', 'inspector')
for name in MODULES:
    path = Path('src/autotalk') / f'{name}.py'
    before = subprocess.check_output(['git', 'show', f'ad4178d:{path}'], text=True)
    after = path.read_text()
    assert ast.dump(ast.parse(before)) == ast.dump(ast.parse(after)), path
    print(f'{path}: AST identical; {len(before.splitlines())} -> {len(after.splitlines())} lines')
print('PASS: all six module ASTs are identical (location attributes excluded).')
