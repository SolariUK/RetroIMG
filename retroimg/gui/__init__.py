"""Optional desktop entry point; importing this module does not require Qt."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


def main(argv: list[str] | None = None) -> int:
    from retroimg import __version__
    parser = argparse.ArgumentParser(description='RetroIMG desktop image converter')
    parser.add_argument('input', type=Path, nargs='?', help='optional image to open')
    parser.add_argument('--version', action='version', version='retroimg-gui ' + __version__)
    parser.add_argument('--presets-dir', type=Path, help='shared JSON preset directory')
    parser.add_argument('--worker', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--smoke-test', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        from .jobs import run_job
        return run_job(args.worker)
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QCoreApplication, QEvent
    except ModuleNotFoundError as exc:
        if exc.name not in ('PySide6', 'PySide6.QtWidgets'):
            raise
        parser.exit(2, 'The desktop frontend needs the GUI extra: pip install "retroimg[gui]"\n')
    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setApplicationName('RetroIMG')
    app.setOrganizationName('RetroIMG')
    if args.smoke_test:
        from .smoke import smoke_test
        return smoke_test(app, args.smoke_test)
    from .window import MainWindow
    window = MainWindow(presets_dir=args.presets_dir)
    window.show()
    if args.input:
        try:
            window.open_image(args.input)
        except (OSError, ValueError) as exc:
            window._set_status('Cannot open image: ' + str(exc))
    try:
        return app.exec()
    finally:
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
