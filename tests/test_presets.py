import json
from pathlib import Path

from PIL import Image
import pytest

from retroimg.cli import build_parser, main
from retroimg.conversion_modes import CONSTRAINED_QUANTIZERS, MODE_OPTIONS
from retroimg.guided import Prompts, run_guided
from retroimg.presets import (
    load_file, load_preset, list_presets, preset_directory, preset_slug, save_preset,
)
from retroimg.profiles import PROFILES
from retroimg.settings import compact_settings, default_settings, normalize_settings


class Replies:
    def __init__(self, answers=None):
        self.answers = answers or {}
        self.questions, self.messages = [], []
        self.ui = Prompts(self.read, self.messages.append)

    def read(self, prompt):
        self.questions.append(prompt)
        for prefix, value in self.answers.items():
            if prompt.startswith(prefix):
                return value.pop(0) if isinstance(value, list) and value else ('' if isinstance(value, list) else value)
        return ''


@pytest.fixture
def paths(tmp_path):
    source, output = tmp_path / 'source.png', tmp_path / 'output.png'
    source_image = Image.new('RGB', (16, 24))
    source_image.putdata([((x*23+y*7)%256, (x*7+y*41)%256, (x*17+y*19)%256)
                         for y in range(24) for x in range(16)])
    source_image.save(source)
    return source, output, tmp_path / 'presets'


def guide(paths, replies, **kwargs):
    return run_guided(paths[0], paths[1], parser=build_parser(), presets_dir=paths[2], ui=replies.ui, **kwargs)


def test_builtin_macaws_matches_the_users_exact_recipe():
    preset = load_preset('builtin:cpc-macaws-bayer2', build_parser())
    expected = dict(profile='cpc-mode1', cpc_mode='constrained', palette='cpc', fit='cover',
                    dither='bayer', bayer_size=2, saturation=1.1, hue_shift=0.0,
                    red_gain=1.0, green_gain=1.0, blue_gain=1.5, scale=2,
                    brightness=1.0, contrast=1.0)
    assert preset.settings == expected
    assert preset.path is None


CASES = [(name, None, 'bitmap') for name in PROFILES]
for name, profile in PROFILES.items():
    for flag, spec in MODE_OPTIONS.items():
        if profile.constraint_model in spec.constraint_models:
            CASES.extend((name, flag, mode) for mode in spec.modes if mode != 'bitmap'
                         and (profile.constraint_model, mode) in CONSTRAINED_QUANTIZERS)


@pytest.mark.parametrize('name,flag,mode', CASES)
def test_round_trip_every_supported_mode(tmp_path, name, flag, mode):
    settings = dict(profile=name, dither='bayer', width=160 if name.startswith('atari') else 16,
                    height=32 if name == 'nes' else 24)
    if flag:
        settings[flag] = mode
    path = tmp_path / 'preset.json'
    saved = save_preset(path, 'A portable preset', 'Example description', settings, build_parser())
    loaded = load_file(path, build_parser())
    assert saved.settings == loaded.settings
    assert loaded.settings['bayer_size'] == 4
    assert loaded.settings['palette'] == PROFILES[name].default_palette
    assert not {'input', 'output', 'preset', 'presets_dir', 'command'} & loaded.settings.keys()
    assert json.loads(path.read_text())['version'] == 1


BAD_SETTINGS = [
    {'input': 'private.jpg'}, {'output': 'private.png'}, {'preset': 'another'}, {'unknown': 1},
    {'profile': 'missing'}, {'palette': 'missing'}, {'scale': True}, {'scale': '2'}, {'scale': 0},
    {'hue_shift': float('nan')}, {'green_gain': -1}, {'saturation': 0}, {'saturation': None},
    {'brightness': -0.1}, {'contrast': -1}, {'brightness': float('inf')},
    {'contrast': float('nan')}, {'brightness': True}, {'contrast': '1.2'},
    {'sharpen': -1}, {'sharpen': 4.1}, {'sharpen': float('nan')},
    {'sharpen': True}, {'sharpen': '1'}, {'sharpen': None},
    {'dither': 'missing'}, {'fit': 'missing'}, {'width': 16}, {'width': 0, 'height': 8},
    {'bayer_size': 4}, {'dither': 'bayer', 'bayer_size': 3},
    {'teletext_mode': 'mosaic', 'width': 15, 'height': 24},
    {'profile': 'cpc-mode0', 'cpc_mode': 'constrained', 'palette': 'c64'},
    {'profile': 'amiga-hires', 'amiga_mode': 'constrained', 'colours': 32},
    {'profile': 'amiga-lores', 'amiga_mode': 'constrained', 'colours': 3},
    {'profile': 'amiga-hires', 'amiga_mode': 'ham'},
    {'profile': 'atari2600-ntsc', 'atari_mode': 'mirror', 'width': 80, 'height': 8},
    {'atari_row_height': 2}, {'colours': 2}, {'cpc_mode': 'constrained'},
]


@pytest.mark.parametrize('settings', BAD_SETTINGS)
def test_invalid_settings_rejected_without_writing(tmp_path, settings):
    path = tmp_path / 'not-created' / 'preset.json'
    with pytest.raises(ValueError):
        save_preset(path, 'Example', '', settings, build_parser())
    assert not path.parent.exists()


@pytest.mark.parametrize('payload', [
    '[]', '{}', '{"version":true,"name":"Bad","settings":{}}',
    '{"version":2,"name":"Future","settings":{}}',
    '{"version":1,"name":"","settings":{}}',
    '{"version":1,"name":"Bad","description":12,"settings":{}}',
    '{"version":1,"name":"Bad","settings":[],"input":"secret.jpg"}',
    '{"version":1,"name":"Bad","settings":{"scale":2,"scale":3}}',
    '{"version":1,"name":"Bad","settings":{"hue_shift":NaN}}',
    '{"version":1,"name":"Bad","settings":{"hue_shift":1e999}}',
])
def test_malformed_files_rejected(tmp_path, payload):
    path = tmp_path / 'bad.json'
    path.write_text(payload)
    with pytest.raises(ValueError):
        load_file(path, build_parser())


def test_listing_lookup_invalid_files_and_ambiguous_names(paths):
    parser = build_parser()
    directory = paths[2]
    entries, errors = list_presets(parser, directory)
    assert len(entries) == 3 and not errors and not directory.exists()
    saved = save_preset(directory / 'cpc-macaws-bayer2.json', 'My own version', '', {}, parser)
    (directory / 'bad.json').write_text('invalid')
    entries, errors = list_presets(parser, directory)
    assert len(entries) == 4 and len(errors) == 1
    assert load_preset(saved.identifier, parser, directory).name == 'My own version'
    assert load_preset(str(saved.path), parser).name == 'My own version'
    with pytest.raises(ValueError, match='ambiguous'):
        load_preset('cpc-macaws-bayer2', parser, directory)
    with pytest.raises(ValueError, match='Cannot load'):
        load_preset(str(directory / 'missing.json'), parser, directory)


def test_default_directory_and_slug(monkeypatch, tmp_path):
    import os
    key = 'APPDATA' if os.name == 'nt' else 'XDG_CONFIG_HOME'
    monkeypatch.setenv(key, str(tmp_path))
    assert preset_directory() == tmp_path / 'retroimg' / 'presets'
    monkeypatch.setenv(key, '')
    assert preset_directory().is_absolute()
    assert preset_slug('../ Macaw / BLUE!') == 'macaw-blue'
    assert '/' not in preset_slug('../../')


def test_exclusive_save_and_atomic_update_failure(paths, monkeypatch):
    import retroimg.presets as module
    path = paths[2] / 'original.json'
    save_preset(path, 'Original', '', {}, build_parser())
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        save_preset(path, 'Replacement', '', {}, build_parser())
    assert path.read_bytes() == original
    def fail(*args):
        raise OSError('simulated replace failure')
    monkeypatch.setattr(module.os, 'replace', fail)
    with pytest.raises(OSError):
        save_preset(path, 'Replacement', '', dict(blue_gain=1.5), build_parser(), replace=True)
    assert path.read_bytes() == original
    assert not list(path.parent.glob('.retroimg-*'))


def test_cli_preset_matches_expanded_command_and_explicit_neutral_override(paths, monkeypatch):
    from retroimg.convert import convert_file
    captured = []
    def capture(*args, **kwargs):
        captured.append(kwargs)
        return convert_file(*args, **kwargs)
    monkeypatch.setattr('retroimg.cli.convert_file', capture)
    source, output, directory = paths
    main(['convert', str(source), str(output), '--preset', 'builtin:cpc-macaws-bayer2',
          '--width=16', '--height=24', '--scale=1', '--blue-g=1', '--dith=none'])
    assert captured[0]['blue_gain'] == 1 and captured[0]['saturation'] == 1.1
    assert captured[0]['bayer_size'] is None and captured[0]['dither'] == 'none'
    direct = output.with_name('direct.png')
    main(['convert', str(source), str(direct), '--profile=cpc-mode1', '--cpc-mode=constrained',
          '--width=16', '--height=24', '--scale=1', '--saturation=1.1'])
    assert output.read_bytes() == direct.read_bytes()


def test_cli_profile_override_resets_inherited_mode_palette_and_colour_count(paths, monkeypatch):
    from retroimg.convert import convert_file
    captured = []
    def capture(*args, **kwargs):
        captured.append(kwargs)
        return convert_file(*args, **kwargs)
    monkeypatch.setattr('retroimg.cli.convert_file', capture)
    source, output, directory = paths
    preset = save_preset(directory / 'lores.json', 'Lores', '',
                        dict(profile='amiga-lores', amiga_mode='constrained', colours=32), build_parser())
    main(['convert', str(source), str(output), '--preset', str(preset.path),
          '--profile=amiga-hires', '--width=16', '--height=24', '--scale=1'])
    assert captured[0]['colours'] == 16
    assert captured[0]['palette_name'] == 'amiga'


def test_tone_preset_round_trip_and_explicit_neutral_cli_override(paths):
    source, output, directory = paths
    parser = build_parser()
    saved = save_preset(directory / 'toned.json', 'Toned', '',
                        dict(brightness=1.1, contrast=1.4, sharpen=1.5, width=16, height=24, scale=1), parser)
    assert load_file(saved.path, parser).settings == saved.settings
    main(['convert', str(source), str(output), '--preset', str(saved.path),
          '--brightness=1.0', '--contrast=1.0', '--sharpen=0'])
    baseline = output.with_name('baseline.png')
    main(['convert', str(source), str(baseline), '--width=16', '--height=24', '--scale=1'])
    assert output.read_bytes() == baseline.read_bytes()


def test_guide_saves_loads_and_edits_tone_controls(paths):
    replies = Replies({'Adjust source': 'yes', 'Brightness': '1.1', 'Contrast': '0.8',
                       'Sharpen': '1.25',
                       'Choose next action': ['save', 'command'], 'Preset name': 'Toned'})
    assert guide(paths, replies) is None
    saved = load_file(paths[2] / 'toned.json', build_parser())
    assert (saved.settings['brightness'], saved.settings['contrast']) == (1.1, 0.8)
    assert saved.settings['sharpen'] == 1.25
    assert any('Source brightness: 1.1; contrast: 0.8' in line for line in replies.messages)
    replies = Replies({'Choose next action': ['edit', 'convert']})
    arguments = guide(paths, replies, preset_reference=str(saved.path))
    settings = build_parser().parse_args(arguments)
    assert (settings.brightness, settings.contrast) == (1.1, 0.8)
    assert settings.sharpen == 1.25
    assert any(question.startswith('Brightness') for question in replies.questions)
    assert '--brightness=1.1' in arguments and '--contrast=0.8' in arguments


def test_cli_invalid_preset_does_not_touch_output(paths, capsys):
    source, output, directory = paths
    output.write_bytes(b'keep')
    directory.mkdir()
    path = directory / 'bad.json'
    path.write_text('{"version":1,"name":"Bad","settings":{"input":"secret"}}')
    with pytest.raises(SystemExit) as exc:
        main(['convert', str(source), str(output), '--preset', str(path)])
    assert exc.value.code == 2
    assert output.read_bytes() == b'keep'
    assert 'unknown preset settings' in capsys.readouterr().err


def test_guide_loads_from_list_and_shows_summary_without_repeating_questions(paths):
    replies = Replies({'Choose starting point': 'load', 'Choose preset': 'builtin:cpc-macaws-bayer2'})
    arguments = guide(paths, replies)
    args = build_parser().parse_args(arguments)
    assert (args.profile, args.cpc_mode, args.bayer_size, args.saturation, args.blue_gain) == (
        'cpc-mode1', 'constrained', 2, 1.1, 1.5)
    assert not any(q.startswith('Choose machine') for q in replies.questions)
    assert any('Settings summary' in message for message in replies.messages)
    assert not paths[1].exists()


def test_guide_save_new_and_update_are_explicit(paths):
    replies = Replies({'Choose next action': ['save', 'command'], 'Preset name': 'My style',
                       'Preset description': 'A portable example'})
    assert guide(paths, replies) is None
    path = paths[2] / 'my-style.json'
    original = path.read_bytes()
    assert not paths[1].exists()
    replies = Replies({'Choose next action': ['edit', 'update', 'command'],
                       'Adjust source': 'yes', 'Blue gain': '1.5'})
    assert guide(paths, replies, preset_reference=str(path)) is None
    assert path.read_bytes() == original  # Update defaults to no.
    replies = Replies({'Choose next action': ['edit', 'update', 'command'],
                       'Adjust source': 'yes', 'Blue gain': '1.5', 'Update My style': 'yes'})
    assert guide(paths, replies, preset_reference=str(path)) is None
    assert load_file(path, build_parser()).settings['blue_gain'] == 1.5
    assert not paths[1].exists()


def test_builtin_is_saved_as_a_copy_and_name_collisions_preserve_existing(paths):
    parser = build_parser()
    before = load_preset('builtin:cpc-macaws-bayer2', parser).settings
    save_preset(paths[2] / 'taken.json', 'Taken', '', {}, parser)
    original = (paths[2] / 'taken.json').read_bytes()
    replies = Replies({'Choose next action': ['save', 'command'], 'Preset name': ['Taken', 'Blue copy']})
    assert guide(paths, replies, preset_reference='builtin:cpc-macaws-bayer2') is None
    assert (paths[2] / 'taken.json').read_bytes() == original
    assert load_file(paths[2] / 'blue-copy.json', parser).settings == before
    assert load_preset('builtin:cpc-macaws-bayer2', parser).settings == before
    assert not any('Update loaded preset: CPC macaws' in msg for msg in replies.messages)


def test_cli_lists_presets_without_creating_directory(paths, capsys):
    main(['presets', '--presets-dir', str(paths[2])])
    assert 'builtin:cpc-macaws-bayer2' in capsys.readouterr().out
    assert not paths[2].exists()


def test_explicit_guide_preset_can_print_without_writing(paths, monkeypatch, capsys):
    monkeypatch.setattr('builtins.input', lambda prompt: pytest.fail('no prompts needed for a loaded print-only preset'))
    main(['guided', str(paths[0]), str(paths[1]), '--preset=builtin:cpc-macaws-bayer2',
          '--presets-dir', str(paths[2]), '--print-only'])
    assert 'blue-gain=1.5' in capsys.readouterr().out
    assert not paths[1].exists() and not paths[2].exists()


def test_inherited_unsupported_modes_reset_but_explicit_invalid_modes_fail():
    from retroimg.settings import merge_settings
    defaults = default_settings(build_parser())
    saved = compact_settings(normalize_settings(dict(profile='amiga-lores', amiga_mode='ham'), defaults))
    merged = merge_settings(saved, dict(profile='amiga-hires'), defaults)
    assert merged['amiga_mode'] == 'bitmap'
    with pytest.raises(ValueError, match='unsupported mode'):
        merge_settings(saved, dict(profile='amiga-hires', amiga_mode='ham'), defaults)


def test_preset_save_failure_returns_to_review(paths, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError('unwritable directory')
    monkeypatch.setattr('retroimg.guided.save_preset', fail)
    replies = Replies({'Choose next action': ['save', 'command'], 'Preset name': 'Example'})
    assert guide(paths, replies) is None
    assert any('Could not save preset' in message for message in replies.messages)
    assert not paths[1].exists()
