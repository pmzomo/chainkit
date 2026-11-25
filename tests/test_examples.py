import runpy
from pathlib import Path

EXAMPLES = Path(__file__).resolve().parent.parent / 'examples'


def test_offline_example_runs(capsys):
    runpy.run_path(str(EXAMPLES / 'inspect_transfer.py'), run_name='__main__')
    out = capsys.readouterr().out
    assert '12.50 USDC' in out and 'unrecognised    nothing' in out and 'signed, size' in out
