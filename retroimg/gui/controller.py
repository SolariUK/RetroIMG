"""Debounced, cancellable rendering in a separate process, with latest-result wins."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile

from PySide6.QtCore import QObject, QProcess, QTimer, Signal


class RenderController(QObject):
    ready = Signal(object)
    failed = Signal(str)
    busyChanged = Signal(bool)

    def __init__(self, parent=None, *, debounce_ms: int = 350):
        super().__init__(parent)
        self._temporary = tempfile.TemporaryDirectory(prefix='retroimg-desktop-')
        self.directory = Path(self._temporary.name)
        self.process = QProcess(self)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._process_error)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(debounce_ms)
        self.timer.timeout.connect(self._start_latest)
        self.revision = 0
        self.pending = None
        self.active = None
        self.last_directory = None
        self._busy = False
        self._closed = False

    def _set_busy(self, value):
        if value != self._busy:
            self._busy = value
            self.busyChanged.emit(value)

    def submit(self, source: Path, *, kind: str, settings: dict | None = None, block_size: int = 8) -> None:
        self.revision += 1
        self.pending = dict(source=str(source.resolve()), kind=kind, settings=dict(settings or {}),
                            block_size=block_size, revision=self.revision)
        self._set_busy(True)
        self.timer.start()

    def _start_latest(self):
        if self._closed or self.pending is None:
            return
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            return
        job = self.pending
        self.pending = None
        directory = self.directory / str(job['revision'])
        directory.mkdir()
        job.update(cache=str(self.directory / 'indexed.json'), image=str(directory / 'preview.png'),
                   response=str(directory / 'response.json'))
        request = directory / 'request.json'
        request.write_text(json.dumps(job, allow_nan=False), encoding='utf-8')
        self.active = job
        arguments = ['--worker', str(request)]
        if not getattr(sys, 'frozen', False):
            arguments = ['-m', 'retroimg.gui', *arguments]
        self.process.start(sys.executable, arguments)

    def _process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self._finished(-1, QProcess.ExitStatus.CrashExit)

    def _finished(self, code, status):
        job, self.active = self.active, None
        if job is None:
            return
        directory = Path(job['response']).parent
        if job['revision'] == self.revision and not self._closed:
            try:
                response = json.loads(Path(job['response']).read_text(encoding='utf-8'))
                if code or 'error' in response:
                    raise ValueError(response.get('error', f'Render process exited with code {code}'))
                if not Path(response['image']).is_file():
                    raise ValueError('The render process did not produce a preview.')
                response['revision'] = job['revision']
                self.ready.emit(response)
                old, self.last_directory = self.last_directory, directory
                if old is not None:
                    shutil.rmtree(old, ignore_errors=True)
            except (OSError, ValueError, KeyError) as exc:
                detail = self.process.readAllStandardError().data().decode('utf-8', errors='replace').strip()
                self.failed.emit(str(exc) if Path(job['response']).exists() else
                                 f'Render process failed: {detail[-1500:] or str(exc)}')
                shutil.rmtree(directory, ignore_errors=True)
        else:
            shutil.rmtree(directory, ignore_errors=True)
        if self.pending is not None and not self.timer.isActive():
            self._start_latest()
        elif self.pending is None:
            self._set_busy(False)

    def cancel(self):
        self.revision += 1
        self.pending = None
        self.timer.stop()
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
        else:
            self._set_busy(False)

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.cancel()
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.waitForFinished(5000)
        self._temporary.cleanup()
