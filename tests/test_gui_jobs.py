"""Desktop work uses the shared converter and invalidates only the necessary stages."""
import json
from pathlib import Path
import subprocess
import sys

from PIL import Image
import pytest

from retroimg.convert import convert_file, convert_to_indexed
from retroimg.gui import jobs
from retroimg.pixelate import pixelate_image


@pytest.fixture
def job(tmp_path):
    source = tmp_path / 'source ; $().png'
    image = Image.new('RGB', (13, 11))
    image.putdata([((x * 19) % 256, (y * 31) % 256, ((x + y) * 23) % 256)
                   for y in range(11) for x in range(13)])
    image.save(source)
    return dict(kind='retro', source=str(source), cache=str(tmp_path / 'indexed.json'),
                image=str(tmp_path / 'preview.png'), response=str(tmp_path / 'response.json'),
                settings=dict(profile='gameboy', gameboy_mode='tiles', width=8, height=8, scale=3))


def test_extracted_conversion_and_worker_match_file_pipeline(job, tmp_path):
    response = jobs.render_job(job)
    settings = dict(job['settings'])
    settings['profile_name'] = settings.pop('profile')
    indexed = convert_file(Path(job['source']), tmp_path / 'cli.png', **settings)
    options = dict(settings)
    options.pop('scale')
    assert convert_to_indexed(Path(job['source']), **options) == indexed
    with Image.open(job['image']) as actual, Image.open(tmp_path / 'cli.png') as expected:
        assert actual.size == expected.size == tuple(response['size'])
        assert actual.tobytes() == expected.tobytes()


def test_display_changes_reuse_indexed_cache_but_source_changes_reconvert(job, monkeypatch):
    original = jobs.convert_to_indexed
    calls = []
    def convert(*args, **kwargs):
        calls.append(kwargs)
        return original(*args, **kwargs)
    monkeypatch.setattr(jobs, 'convert_to_indexed', convert)
    assert not jobs.render_job(job)['reused_conversion']
    job['settings'].update(scale=4, display_effect='crt-aperture', bloom_strength=.25,
                            rf_strength=.35, chromatic_strength=.25, display_brightness=1.2)
    assert jobs.render_job(job)['reused_conversion']
    assert len(calls) == 1
    job['settings']['contrast'] = 1.2
    assert not jobs.render_job(job)['reused_conversion']
    assert len(calls) == 2
    Image.new('RGB', (13, 11), (255, 0, 0)).save(job['source'])
    assert not jobs.render_job(job)['reused_conversion']
    assert len(calls) == 3


def test_broken_cache_is_rebuilt_and_errors_preserve_last_render(job):
    Path(job['cache']).write_text('{broken')
    assert not jobs.render_job(job)['reused_conversion']
    existing = Path(job['image']).read_bytes()
    job['settings']['display_effect'] = 'unknown'
    request = Path(job['image']).with_name('request.json')
    request.write_text(json.dumps(job))
    assert jobs.run_job(request) == 1
    assert 'unknown display effect' in json.loads(Path(job['response']).read_text())['error']
    assert Path(job['image']).read_bytes() == existing


def test_pixelation_worker_preserves_original_rgb_and_dimensions(job):
    job.update(kind='pixelate', block_size=4)
    response = jobs.render_job(job)
    with Image.open(job['source']) as source, Image.open(job['image']) as actual:
        expected = pixelate_image(source, 4)
        assert actual.size == source.size == (13, 11)
        assert actual.tobytes() == expected.tobytes()
    assert response['palette_size'] is None and not response['reused_conversion']


def test_desktop_entry_and_worker_import_without_loading_qt():
    script = "import sys; import retroimg.gui; import retroimg.gui.jobs; assert 'PySide6' not in sys.modules"
    subprocess.run([sys.executable, '-c', script], check=True)
    result = subprocess.run([sys.executable, '-m', 'retroimg.gui', '--version'], capture_output=True, text=True, check=True)
    assert result.stdout.startswith('retroimg-gui ')
