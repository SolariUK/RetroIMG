from pathlib import Path
import shlex
import subprocess
import sys

from PIL import Image
import pytest

from retroimg.cli import build_parser, main
from retroimg.conversion_modes import CONSTRAINED_QUANTIZERS, MODE_OPTIONS
from retroimg.guided import (
    Prompts, build_convert_arguments, format_command, palette_choices,
    profile_modes, run_guided,
)
from retroimg.profiles import PROFILES


class Replies:
    """Respond by prompt name; an empty reply accepts the displayed default."""
    def __init__(self, answers=None):
        self.answers = {} if answers is None else dict(answers)
        self.messages = []
        self.questions = []
        self.ui = Prompts(self.read, self.messages.append)

    def read(self, prompt):
        self.questions.append(prompt)
        for prefix, value in self.answers.items():
            if prompt.startswith(prefix):
                return value.pop(0) if isinstance(value, list) and value else ('' if isinstance(value, list) else value)
        return ''


@pytest.fixture
def paths(tmp_path):
    source, output = tmp_path / "source ' $().png", tmp_path / 'output ; image.png'
    image = Image.new('RGB', (32, 24))
    image.putdata([((x*23+y*7)%256, (x*7+y*41)%256, (x*17+y*19)%256)
                   for y in range(24) for x in range(32)])
    image.save(source)
    return source, output


def guide(paths, replies=None, **kwargs):
    replies = Replies() if replies is None else replies
    return run_guided(*paths, parser=build_parser(), ui=replies.ui, **kwargs)


def test_defaults_build_an_ordinary_command_without_writing(paths):
    replies = Replies()
    arguments = guide(paths, replies)
    args = build_parser().parse_args(arguments)
    assert (args.profile, args.teletext_mode, args.palette, args.dither, args.scale) == (
        'teletext', 'bitmap', 'teletext', 'none', 8)
    assert not paths[1].exists()
    assert any('Settings summary' in message for message in replies.messages)
    assert any('Preview: 640x600' in message for message in replies.messages)
    assert shlex.split(format_command(arguments, platform='posix'))[1:] == arguments


def test_guide_distinguishes_source_and_display_brightness(paths):
    replies = Replies({'Adjust source': 'yes', 'Brightness': '1.1',
                       'Choose display effect': 'crt-aperture', 'Display brightness': '2'})
    arguments = guide(paths, replies)
    args = build_parser().parse_args(arguments)
    assert args.brightness == 1.1 and args.display_brightness == 2
    assert any('Source brightness: 1.1' in message for message in replies.messages)
    assert any('Display brightness: 2.0 (after display effects)' in message for message in replies.messages)
    assert any('Display brightness (after effects' in question for question in replies.questions)


def test_guide_pixelates_original_colours_without_machine_questions(paths):
    replies = Replies({'Choose starting point': 'pixelate', 'Pixel block size': '4'})
    arguments = guide(paths, replies)
    args = build_parser().parse_args(arguments)
    assert args.command == 'pixelate' and args.block_size == 4
    assert not any(q.startswith('Choose machine') for q in replies.questions)
    main(arguments)
    with Image.open(paths[0]) as source, Image.open(paths[1]) as result:
        assert result.size == source.size
    assert any('original RGB colours' in message for message in replies.messages)


def test_guide_combines_bloom_with_crt_and_retains_settings_when_editing(paths):
    replies = Replies({'Choose display effect': 'crt-aperture', 'Add highlight bloom': 'yes',
                       'Bloom strength': ['.4', ''], 'Bloom radius': ['1.5', ''],
                       'Choose next action': ['edit', 'convert']})
    arguments = guide(paths, replies)
    args = build_parser().parse_args(arguments)
    assert (args.display_effect, args.bloom_strength, args.bloom_radius) == ('crt-aperture', .4, 1.5)
    assert any('before display brightness' in message for message in replies.messages)
    replies = Replies({'Add highlight bloom': ['yes', 'no'], 'Choose next action': ['edit', 'convert']})
    assert build_parser().parse_args(guide(paths, replies)).bloom_strength == 0


def test_guide_combines_chromatic_aberration_with_crt_and_bloom(paths):
    replies = Replies({'Choose display effect': 'crt-aperture', 'Add chromatic aberration': 'yes',
                       'Chromatic strength': ['.6', ''], 'Add highlight bloom': 'yes',
                       'Choose next action': ['edit', 'convert']})
    args = build_parser().parse_args(guide(paths, replies))
    assert (args.display_effect, args.chromatic_strength, args.bloom_strength) == ('crt-aperture', .6, .25)
    assert any('Chromatic aberration: 0.6 (before display treatment)' in line for line in replies.messages)
    replies = Replies({'Add chromatic aberration': ['yes', 'no'], 'Choose next action': ['edit', 'convert']})
    assert build_parser().parse_args(guide(paths, replies)).chromatic_strength == 0


def test_guide_pixelation_print_only_and_block_size_revision(paths):
    replies = Replies({'Choose starting point': 'pixelate', 'Pixel block size': '16'})
    assert guide(paths, replies, print_only=True) is None
    assert not paths[1].exists()
    assert any('--block-size=16' in message for message in replies.messages)
    replies = Replies({'Choose starting point': 'pixelate', 'Pixel block size': ['4', '8'],
                       'Choose next action': ['edit', 'convert']})
    args = build_parser().parse_args(guide(paths, replies))
    assert args.command == 'pixelate' and args.block_size == 8


@pytest.mark.parametrize('effect', ['gameboy-lcd', 'scanlines', 'crt-aperture'])
@pytest.mark.parametrize('machine', ['gameboy', 'teletext'])
def test_display_effect_is_explicit_and_available_for_other_machines(paths, machine, effect):
    replies = Replies({'Choose machine': machine, 'Choose display effect': effect,
                       'Display effect strength': '.8', 'Preview scale': '6'})
    arguments = guide(paths, replies)
    args = build_parser().parse_args(arguments)
    assert args.display_effect == effect and args.effect_strength == .8 and args.scale == 6
    assert any(f'Display effect: {effect}; strength: 0.8' in message for message in replies.messages)


CASES = []
for name, profile in PROFILES.items():
    CASES.append((name, None, 'bitmap'))
    for option, spec in MODE_OPTIONS.items():
        if profile.constraint_model in spec.constraint_models:
            CASES.extend((name, option, mode) for mode in spec.modes if mode != 'bitmap'
                         and (profile.constraint_model, mode) in CONSTRAINED_QUANTIZERS)


@pytest.mark.parametrize('name,option,mode', CASES)
def test_every_profile_and_supported_mode_builds_and_runs(paths, name, option, mode):
    replies = Replies({
        'Choose machine': name.split('-', 1)[0], 'Choose profile': name,
        'Choose conversion mode': mode, 'Use a custom': 'yes',
        'Logical width': '160' if name.startswith('atari') and mode != 'bitmap' else '16',
        'Logical height': '32' if name == 'nes' else '24', 'Choose dithering': 'bayer', 'Choose bayer matrix': '8',
        'Adjust source': 'yes', 'Brightness': '1.1', 'Contrast': '1.2',
        'Preview scale': '1',
    })
    arguments = guide(paths, replies)
    args = build_parser().parse_args(arguments)
    assert args.profile == name
    assert args.palette == PROFILES[name].default_palette
    assert args.bayer_size == 8
    assert (args.brightness, args.contrast) == (1.1, 1.2)
    if option:
        assert getattr(args, option) == mode
    main(arguments)
    with Image.open(paths[1]) as image:
        image.verify()


def test_only_applicable_modes_and_palettes_are_offered():
    assert profile_modes(PROFILES['amiga-hires'])[1] == ('bitmap', 'constrained')
    assert profile_modes(PROFILES['amiga-lores'])[1] == ('bitmap', 'constrained', 'ehb', 'ham')
    assert profile_modes(PROFILES['c64-hires']) == (None, ('bitmap',))
    cpc = PROFILES['cpc-mode0']
    assert palette_choices(cpc, 'constrained', 'cpc_mode') == ('cpc',)
    assert 'c64' in palette_choices(cpc, 'bitmap', 'cpc_mode')
    assert 'amiga' in palette_choices(PROFILES['teletext'], 'mosaic', 'teletext_mode')
    assert set(palette_choices(PROFILES['atari2600-pal'], 'mirror', 'atari_mode')) == {
        'atari2600-pal', 'atari2600-ntsc'}


def test_numeric_choices_use_actual_values_not_ambiguous_menu_numbers():
    replies = Replies({'Choose size': ['3', '2']})
    assert replies.ui.choice('Size', [('2', '2x2'), ('4', '4x4'), ('8', '8x8')], '4') == '2'
    assert not any('2. 4x4' in message for message in replies.messages)
    assert any('listed' in message for message in replies.messages)


def test_prompts_retry_invalid_menu_and_numeric_input():
    replies = Replies({'Choose mode': ['bad', '99', '2'], 'Number': ['nan', 'inf', '-1', '1.5', '4'],
                       'Continue': ['maybe', 'yes']})
    assert replies.ui.choice('Mode', [('a', 'First'), ('b', 'Second')], 'a') == 'b'
    assert replies.ui.number('Number', 2, integer=True, valid=lambda n: n > 0) == 4
    assert replies.ui.yes_no('Continue')


def test_geometry_validation_and_finite_colour_controls(paths):
    replies = Replies({'Choose conversion mode': 'mosaic', 'Use a custom': 'yes',
        'Logical width': ['15', '16'], 'Logical height': ['7', '24'],
        'Adjust source': 'yes', 'Saturation': ['nan', '0', '1.2'],
        'Brightness': ['nan', '-1', '1.1'], 'Contrast': ['inf', '-1', '0'],
        'Hue shift': ['inf', '-20'], 'Green gain': ['-1', '1.15'], 'Preview scale': ['0', '2']})
    args = build_parser().parse_args(guide(paths, replies))
    assert (args.width, args.height, args.saturation, args.hue_shift, args.green_gain, args.scale) == (
        16, 24, 1.2, -20, 1.15, 2)
    assert (args.brightness, args.contrast) == (1.1, 0)
    assert any('divisible by 2' in message for message in replies.messages)
    assert any('divisible by 3' in message for message in replies.messages)


def test_unrestricted_palette_swap_and_atari_fixed_width(paths):
    replies = Replies({'Choose machine': 'cpc', 'Choose profile': 'cpc-mode0', 'Choose palette': 'c64'})
    args = build_parser().parse_args(guide(paths, replies))
    assert args.cpc_mode == 'bitmap' and args.palette == 'c64'
    replies = Replies({'Choose machine': 'atari2600', 'Choose conversion mode': 'mirror',
                       'Use a custom': 'yes', 'Logical height': '5', 'Row height': '3'})
    args = build_parser().parse_args(guide(paths, replies))
    assert (args.width, args.height, args.atari_row_height) == (160, 5, 3)
    assert not any(question.startswith('Logical width') for question in replies.questions)


def test_edit_retains_settings_as_defaults(paths):
    replies = Replies({'Choose machine': ['cpc', ''], 'Choose profile': ['cpc-mode0', ''],
        'Choose palette': ['c64', ''], 'Use a custom': ['yes', ''],
        'Logical width': ['16', ''], 'Logical height': ['24', ''],
        'Choose dithering': ['bayer', ''], 'Choose bayer matrix': ['8', ''],
        'Adjust source': ['yes', ''], 'Hue shift': ['20', ''], 'Green gain': ['1.15', ''],
        'Brightness': ['1.1', ''], 'Contrast': ['1.2', ''],
        'Choose next action': ['edit', 'convert']})
    args = build_parser().parse_args(guide(paths, replies))
    assert (args.profile, args.palette, args.width, args.height, args.bayer_size, args.hue_shift, args.green_gain) == (
        'cpc-mode0', 'c64', 16, 24, 8, 20, 1.15)
    assert (args.brightness, args.contrast) == (1.1, 1.2)


def test_edit_discards_settings_that_no_longer_apply(paths):
    replies = Replies({'Choose machine': ['cpc', 'amiga'], 'Choose profile': ['cpc-mode0', 'amiga-hires'],
        'Choose conversion mode': 'constrained', 'Use a custom': ['yes', 'no'],
        'Logical width': '16', 'Logical height': '24', 'Choose dithering': ['bayer', 'none'],
        'Choose bayer matrix': '8', 'Adjust source': ['yes', 'no'], 'Hue shift': '20',
        'Choose next action': ['edit', 'convert']})
    arguments = guide(paths, replies)
    args = build_parser().parse_args(arguments)
    assert (args.profile, args.amiga_mode, args.colours) == ('amiga-hires', 'constrained', 16)
    assert args.bayer_size is None and args.width is None and args.height is None
    assert args.hue_shift == 0 and args.cpc_mode == 'bitmap'
    assert not any(arg.startswith('--cpc-mode') for arg in arguments)


@pytest.mark.parametrize('action', ['command', 'cancel', 'q'])
def test_command_only_and_cancellation_never_write(paths, action):
    assert guide(paths, Replies({'Choose next action': action})) is None
    assert not paths[1].exists()


def test_print_only_does_not_execute_conversion(paths, monkeypatch, capsys):
    monkeypatch.setattr('builtins.input', lambda prompt: '')
    monkeypatch.setattr('retroimg.cli.convert_file', lambda *args, **kwargs: pytest.fail('must not convert'))
    main(['guided', str(paths[0]), str(paths[1]), '--print-only'])
    assert not paths[1].exists()
    assert 'Equivalent command' in capsys.readouterr().out


@pytest.mark.parametrize('exception', [EOFError, KeyboardInterrupt])
def test_eof_and_interrupt_cancel_cleanly(paths, exception):
    def stop(prompt):
        raise exception
    messages = []
    assert run_guided(*paths, parser=build_parser(), ui=Prompts(stop, messages.append)) is None
    assert any('Cancelled' in message for message in messages)
    assert not paths[1].exists()


def test_optional_paths_invalid_input_and_output_retry(paths, tmp_path):
    invalid = tmp_path / 'invalid.png'
    invalid.write_text('not an image')
    replies = Replies({'Input image': [str(invalid), str(paths[0])], 'Output image': [
        str(paths[0]), str(tmp_path / 'missing' / 'out.png'), str(tmp_path),
        str(tmp_path / 'bad.extension'), str(paths[1])]})
    arguments = run_guided(None, None, parser=build_parser(), ui=replies.ui)
    args = build_parser().parse_args(arguments)
    assert args.input == paths[0] and args.output == paths[1]
    assert any('Cannot read' in message for message in replies.messages)
    assert any('different from' in message for message in replies.messages)
    assert any('directory does not exist' in message for message in replies.messages)
    assert any('supported output' in message for message in replies.messages)


def test_existing_output_requires_explicit_replacement_and_print_only_does_not(paths):
    paths[1].write_bytes(b'keep')
    assert guide(paths) is None
    assert paths[1].read_bytes() == b'keep'
    arguments = guide(paths, Replies({'Output already exists': 'yes'}))
    assert arguments is not None and paths[1].read_bytes() == b'keep'  # Builder still does no conversion.
    replies = Replies()
    assert guide(paths, replies, print_only=True) is None
    assert not any('Replace it' in question for question in replies.questions)


def test_command_tokens_handle_metacharacters_and_negative_scientific_notation(paths):
    arguments = build_convert_arguments(*paths, {'profile': 'teletext', 'hue_shift': -1e20})
    assert build_parser().parse_args(arguments).hue_shift == -1e20
    assert shlex.split(format_command(arguments, platform='posix')) == ['retroimg', *arguments]
    windows = format_command(['convert', "C:\\a'b; $(run) %X%.png", 'out.png'], platform='nt')
    assert windows == "& 'retroimg' 'convert' 'C:\\a''b; $(run) %X%.png' 'out.png'"


def test_guided_cli_matches_its_printed_normal_command(paths, monkeypatch, capsys):
    # Parse POSIX quoting explicitly; PowerShell quoting has a separate test.
    monkeypatch.setattr('retroimg.guided.format_command',
                        lambda arguments: format_command(arguments, platform='posix'))
    replies = Replies({'Choose machine': 'cpc', 'Choose profile': 'cpc-mode0',
        'Choose conversion mode': 'constrained', 'Use a custom': 'yes',
        'Logical width': '16', 'Logical height': '24', 'Choose image fitting': 'stretch',
        'Choose dithering': 'bayer', 'Choose bayer matrix': '8', 'Adjust source': 'yes',
        'Hue shift': '20', 'Green gain': '1.15', 'Preview scale': '2'})
    monkeypatch.setattr('builtins.input', replies.read)
    main(['guided', str(paths[0]), str(paths[1])])
    output = capsys.readouterr().out
    command = next(line for line in output.splitlines() if line.startswith('retroimg convert '))
    arguments = shlex.split(command)[1:]
    expected = paths[1].with_name('direct.png')
    arguments[2] = str(expected)
    main(arguments)
    assert paths[1].read_bytes() == expected.read_bytes()


def test_piped_defaults_and_eof_work_without_a_terminal(paths):
    command = [sys.executable, '-m', 'retroimg.cli', 'guided', str(paths[0]), str(paths[1])]
    result = subprocess.run(command, input='', text=True, capture_output=True, check=True)
    assert 'Cancelled' in result.stdout and not paths[1].exists()
    result = subprocess.run(command, input='\n' * 40, text=True, capture_output=True, check=True)
    assert paths[1].is_file() and 'Wrote' in result.stdout


def test_normal_cli_does_not_load_guided_module():
    subprocess.run([sys.executable, '-c',
        'import retroimg.cli; import sys; assert "retroimg.guided" not in sys.modules'], check=True)


def test_constraint_change_replaces_incompatible_dimension_defaults(paths):
    replies = Replies({'Choose conversion mode': ['bitmap', 'mosaic'],
        'Use a custom': ['yes', ''], 'Logical width': ['13', ''], 'Logical height': ['7', ''],
        'Choose next action': ['edit', 'convert']})
    args = build_parser().parse_args(guide(paths, replies))
    assert args.teletext_mode == 'mosaic'
    assert (args.width, args.height) == (80, 75)


def test_changing_to_constrained_mode_resets_an_incompatible_palette(paths):
    replies = Replies({'Choose machine': 'cpc', 'Choose profile': 'cpc-mode0',
        'Choose conversion mode': ['bitmap', 'constrained'], 'Choose palette': 'c64',
        'Choose next action': ['edit', 'convert']})
    args = build_parser().parse_args(guide(paths, replies))
    assert args.cpc_mode == 'constrained' and args.palette == 'cpc'


def test_default_output_path_is_beside_source(paths):
    arguments = run_guided(paths[0], None, parser=build_parser(), ui=Replies().ui)
    args = build_parser().parse_args(arguments)
    assert args.output == paths[0].with_name(paths[0].stem + '-retro.png')
    assert not args.output.exists()


def test_guided_conversion_failure_is_a_clean_cli_error(paths, monkeypatch, capsys):
    monkeypatch.setattr('builtins.input', lambda prompt: '')
    def fail(*args, **kwargs):
        raise OSError('example write failure')
    monkeypatch.setattr('retroimg.cli.convert_file', fail)
    with pytest.raises(SystemExit) as exc:
        main(['guided', str(paths[0]), str(paths[1])])
    assert exc.value.code == 1
    assert 'Conversion failed: example write failure' in capsys.readouterr().err
