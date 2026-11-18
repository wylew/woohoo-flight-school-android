"""Android build steps 1-3 (BuildTask.java calls these through Chaquopy): verify the player's dump, extract what the game
reads at run time, translate its ARM code to C. Step 4 (compile) is native (libtcc, NativeCompiler.java).

The repository's own tools do the work unchanged: tools/pipeline.py, tools/cia.py, tools/funcs.py and recomp/arm2c.py are
copied into the APK's Python sources by app/build.gradle. logger is a Java object with a log(String) method."""
import contextlib
import io
import os
import runpy
import sys

import cia
import pipeline


def _prune_path():
    """Drop a repository-layout <...>/tools entry (pipeline.py and arm2c.py add one on the PC). In the APK that folder
    doesn't exist, and Chaquopy's asset importer raises FileNotFoundError for it instead of skipping it as CPython does."""
    sys.path[:] = [p for p in sys.path if not (os.path.basename(os.path.normpath(p)) == 'tools' and not os.path.isdir(p))]


_prune_path()


class _Lines(io.TextIOBase):
    """stdout/stderr -> logger.log, line by line"""
    def __init__(self, logger): self.logger, self.buf = logger, ''
    def writable(self): return True
    def write(self, s):
        self.buf += s
        while '\n' in self.buf:
            line, self.buf = self.buf.split('\n', 1)
            if line.strip(): self.logger.log(line)
        return len(s)
    def flush(self):
        if self.buf.strip(): self.logger.log(self.buf)
        self.buf = ''


def verify(rom, logger):
    """'' when the dump is supported, else the problems, one per line"""
    try:
        r = pipeline.verify(rom, log=logger.log)
    except pipeline.PipelineError as e:
        return str(e)
    return '' if r['ok'] else '\n'.join(r['problems'])


def code_sha256(rom):
    return pipeline.verify(rom, log=lambda m: None).get('code_sha256', '')


def extract(rom, out_dir, logger):
    cia.extract(rom, out_dir, runtime_only=True, log=logger.log)


def recompile(extracted_dir, gen_dir, seeds_file, logger):
    """recomp/arm2c.py <code.bin> <exheader.bin> <gen dir>, as the desktop pipeline runs it"""
    os.environ['PWR_EXTRA_SEEDS'] = seeds_file
    argv = sys.argv
    sys.argv = ['arm2c.py', os.path.join(extracted_dir, 'code.bin'), os.path.join(extracted_dir, 'exheader.bin'), gen_dir]
    out = _Lines(logger)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            _prune_path()
            runpy.run_module('arm2c', run_name='__main__')
    finally:
        out.flush()
        sys.argv = argv
