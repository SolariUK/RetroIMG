"""Path candidates and real Tab entry without requiring a physical terminal."""
import asyncio
import ntpath
import os
from types import SimpleNamespace

from PIL import Image
import pytest

pytest.importorskip('prompt_toolkit')

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from retroimg import path_input
from retroimg.cli import build_parser
from retroimg.guided import GuidedCancelled, Prompts, run_guided


def candidates(text):
    return [text + completion.text for completion in
            path_input.DirectoryPathCompleter().get_completions(
                Document(text), CompleteEvent(completion_requested=True))]


def terminal(monkeypatch, stdin=True, stdout=True):
    monkeypatch.setattr(path_input, 'sys', SimpleNamespace(
        stdin=SimpleNamespace(isatty=lambda: stdin),
        stdout=SimpleNamespace(isatty=lambda: stdout)))


@pytest.fixture
def tree(tmp_path, monkeypatch):
    (tmp_path / 'Pictures with spaces').mkdir()
    (tmp_path / 'Pictures with spaces' / 'macaw é.png').touch()
    (tmp_path / 'portrait.png').touch()
    (tmp_path / 'portrait.jpg').touch()
    (tmp_path / '.hidden.png').touch()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('USERPROFILE', str(tmp_path))
    return tmp_path


def test_candidates_preserve_literal_paths_and_add_directory_separator(tree):
    assert candidates('Pic') == ['Pictures with spaces' + os.sep]
    assert candidates('Pictures with spaces/mac') == ['Pictures with spaces/macaw é.png']
    assert candidates(str(tree / 'Pic')) == [str(tree / 'Pictures with spaces') + os.sep]
    assert candidates('~/Pic') == ['~/Pictures with spaces/']
    assert candidates('./por') == ['./portrait.jpg', './portrait.png']
    assert candidates('.hid') == ['.hidden.png']


def test_missing_directory_and_new_output_filename_are_allowed(tree):
    assert candidates('missing-directory/image') == []
    assert candidates('brand-new-output.png') == []


@pytest.mark.parametrize('prefix,expected', [
    ('Pictures with spaces/mac', 'Pictures with spaces/macaw é.png'),
    ('Pic', 'Pictures with spaces' + os.sep),
    ('~/Pictures with spaces/mac', '~/Pictures with spaces/macaw é.png'),
    ('new-output.png', 'new-output.png'),
    ('', ''),
])
def test_actual_tab_and_enter(tree, monkeypatch, prefix, expected):
    terminal(monkeypatch)
    with create_pipe_input() as keys:
        session = PromptSession(input=keys, output=DummyOutput())
        async def enter_path(message, **kwargs):
            task = asyncio.create_task(session.prompt_async(message, **kwargs))
            keys.send_text(prefix + ('\t' if prefix else ''))
            # Tab completion runs asynchronously. Wait for its result before Enter.
            try:
                for _ in range(100):
                    await asyncio.sleep(0.01)
                    if session.default_buffer.text == expected:
                        break
                keys.send_text('\r')
                return await asyncio.wait_for(task, timeout=2)
            finally:
                if not task.done():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
        monkeypatch.setattr(path_input, 'prompt', lambda message, **kwargs:
                            asyncio.run(enter_path(message, **kwargs)))
        assert path_input.read_path('Path: ', fallback=lambda _: pytest.fail('plain input')) == expected


@pytest.mark.parametrize('key,exception', [('\x03', KeyboardInterrupt), ('\x04', EOFError)])
def test_actual_terminal_cancellation(monkeypatch, key, exception):
    terminal(monkeypatch)
    with create_pipe_input() as keys:
        session = PromptSession(input=keys, output=DummyOutput())
        monkeypatch.setattr(path_input, 'prompt', session.prompt)
        keys.send_text(key)
        with pytest.raises(exception):
            path_input.read_path('Path: ', fallback=lambda _: pytest.fail('plain input'))


@pytest.mark.parametrize('stdin,stdout', [(False, False), (True, False), (False, True)])
def test_redirected_streams_use_plain_input(monkeypatch, stdin, stdout):
    terminal(monkeypatch, stdin, stdout)
    monkeypatch.setattr(path_input, 'prompt', lambda *a, **k: pytest.fail('terminal prompt'))
    assert path_input.read_path('Path: ', fallback=lambda _: 'new file.png') == 'new file.png'


@pytest.mark.parametrize('prefix,expected', [
    ('C:\\Users\\Sol\\Pic', 'C:\\Users\\Sol\\Pictures with spaces\\'),
    ('C:/Users/Sol/Pic', 'C:/Users/Sol/Pictures with spaces/'),
    ('C:\\Users\\Sol\\Pictures with spaces\\mac', 'C:\\Users\\Sol\\Pictures with spaces\\macaw é.png'),
    ('\\\\server\\share\\Pic', '\\\\server\\share\\Pictures with spaces\\'),
])
def test_windows_drive_and_unc_path_semantics(monkeypatch, prefix, expected):
    # Exercise the real completer with Windows path rules, using a virtual FS.
    import prompt_toolkit.completion.filesystem as filesystem
    directories = {ntpath.normcase(ntpath.normpath(p)) for p in (
        'C:/Users/Sol', 'C:/Users/Sol/Pictures with spaces',
        '//server/share/', '//server/share/Pictures with spaces')}
    paths = SimpleNamespace(**{name: getattr(ntpath, name) for name in
                               ('dirname', 'basename', 'join', 'expanduser')},
                            isdir=lambda p: ntpath.normcase(ntpath.normpath(p)) in directories)
    fake_os = SimpleNamespace(path=paths, sep='\\',
                              listdir=lambda p: ['macaw é.png'] if 'Pictures' in p else ['Pictures with spaces'])
    monkeypatch.setattr(path_input, 'os', fake_os)
    monkeypatch.setattr(filesystem, 'os', fake_os)
    assert candidates(prefix) == [expected]


def test_completion_only_runs_for_path_prompts(monkeypatch):
    calls = []
    monkeypatch.setattr(path_input, 'read_path', lambda message, **kwargs:
                        calls.append(message) or ' completed path.png ')
    monkeypatch.setattr('builtins.input', lambda _: 'menu')
    ui = Prompts()
    assert ui.answer('Image: ', path=True) == 'completed path.png'
    assert ui.answer('Menu: ') == 'menu'
    assert calls == ['Image: ']
    assert Prompts(read=lambda _: 'injected').answer('Image: ', path=True) == 'injected'


def test_completed_cancel_value_uses_existing_cancellation(monkeypatch):
    monkeypatch.setattr(path_input, 'read_path', lambda *a, **k: 'q')
    with pytest.raises(GuidedCancelled):
        Prompts().answer('Image: ', path=True)


def test_guide_uses_completion_for_both_paths_and_keeps_conversion_separate(tmp_path, monkeypatch):
    source, output = tmp_path / 'source image.png', tmp_path / 'new output.png'
    Image.new('RGB', (4, 4)).save(source)
    answers = iter([str(source), str(output)])
    calls = []
    def read_path(message, **kwargs):
        calls.append(message)
        return next(answers)
    monkeypatch.setattr(path_input, 'read_path', read_path)
    monkeypatch.setattr('builtins.input', lambda _: '')
    arguments = run_guided(None, None, parser=build_parser(), ui=Prompts(write=lambda _: None))
    assert arguments[1:3] == [str(source), str(output)]
    assert len(calls) == 2
    assert all('Tab to complete' in call for call in calls)
    assert not output.exists()
