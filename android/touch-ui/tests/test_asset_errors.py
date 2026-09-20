"""Execute native fatal reporting in separate processes; no game or Activity is started."""
from pathlib import Path
import os, subprocess, sys, tempfile
exe=str(Path(sys.argv[1]).resolve())
with tempfile.TemporaryDirectory() as d:
    target=Path(d)/'startup_error.test.txt'
    for mode,phrase in [('missing','nitrofs.tsv'),('mismatch','different revision')]:
        p=subprocess.run([exe,mode],env={**os.environ,'SM64DS_ERROR_DIR':d,'SM64DS_INSTANCE':'test'},capture_output=True,text=True)
        assert p.returncode==2,(mode,p.returncode)
        assert phrase in target.read_text() and phrase in p.stderr
    target.unlink();valuable=Path(d)/'keep.txt';valuable.write_text('do not overwrite')
    target.symlink_to(valuable)
    assert subprocess.run([exe],env={**os.environ,'SM64DS_ERROR_DIR':d,'SM64DS_INSTANCE':'test'},capture_output=True).returncode==2
    assert valuable.read_text()=='do not overwrite'
    assert subprocess.run([exe],env={k:v for k,v in os.environ.items() if k!='SM64DS_ERROR_DIR'},capture_output=True).returncode==2
print('PASS: fatal exit codes, both reports, no symlink overwrite and no guessed directory')
