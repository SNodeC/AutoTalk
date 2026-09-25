"""Private JIT compiler driver; no compiler or CUDA toolkit is required on PATH."""
import os
import sys
from pathlib import Path

import ziglang

arguments = sys.argv[2:]
directories = [Path(arg[2:]) for arg in arguments if arg.startswith("-L")]
# Resolve GNU's exact-library syntax before invoking Zig's linker. This also
# works with an empty PATH, where no system linker helpers are discoverable.
for index, argument in enumerate(arguments):
    if argument.startswith("-l:"):
        library = next((directory / argument[3:] for directory in directories
                        if (directory / argument[3:]).is_file()), None)
        if library is not None:
            arguments[index] = str(library.resolve())
compiler = str(Path(ziglang.__file__).parent / "zig")
os.execv(compiler, [compiler, sys.argv[1], *arguments])
