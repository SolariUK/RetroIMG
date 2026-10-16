import pytest

from retroimg import __version__
from retroimg.cli import main


def test_cli_reports_package_version_without_a_subcommand(capsys):
    with pytest.raises(SystemExit) as result:
        main(['--version'])
    assert result.value.code == 0
    assert capsys.readouterr().out == f'retroimg {__version__}\n'
