"""Exercise the actual desktop and child worker for installed/frozen build checks."""
import json
from pathlib import Path
import tempfile

from PIL import Image
from PySide6.QtCore import QCoreApplication, QEvent, QTimer

from retroimg.convert import convert_file
from .window import MainWindow


def smoke_test(app, report: Path) -> int:
    with tempfile.TemporaryDirectory(prefix='retroimg-gui-smoke-') as temporary:
        directory = Path(temporary)
        source = directory / 'source image.png'
        image = Image.new('RGB', (32, 32))
        image.putdata([((x * 29) % 256, (y * 37) % 256, ((x + y) * 17) % 256)
                       for y in range(32) for x in range(32)])
        image.save(source)
        window = MainWindow(presets_dir=directory / 'presets')
        window.options.set_settings(dict(profile='gameboy', gameboy_mode='tiles', width=16, height=16,
                                         scale=3, display_effect='crt-aperture'))
        state = {'stage': 0, 'ok': False}

        def finish(error=None):
            if error:
                state['error'] = str(error)
            window.close()
            app.exit(1 if error else 0)

        def ready(response):
            try:
                if state['stage'] == 0:
                    expected = directory / 'reference.png'
                    options = window.options.settings()
                    options['profile_name'] = options.pop('profile')
                    options['palette_name'] = options.pop('palette')
                    convert_file(source, expected, **options)
                    actual = directory / 'exported.png'
                    window.export_to(actual)
                    with Image.open(expected) as reference, Image.open(actual) as exported:
                        assert reference.size == exported.size == (48, 48)
                        assert reference.tobytes() == exported.tobytes()
                    assert not response['reused_conversion']
                    state['stage'] = 1
                    window.options.fields['bloom_strength'].setValue(.25)
                else:
                    assert response['reused_conversion']
                    assert response['size'] == [48, 48]
                    preset = directory / 'shared-preset.json'
                    window.save_preset_to(preset)
                    window.options.set_settings({})
                    window.load_preset_path(preset)
                    assert window.options.settings()['bloom_strength'] == .25
                    state.update(ok=True, size=response['size'], reused_conversion=True)
                    finish()
            except Exception as exc:
                finish(str(exc) or type(exc).__name__)

        window.controller.ready.connect(ready)
        window.controller.failed.connect(finish)
        timeout = QTimer()
        timeout.setSingleShot(True)
        timeout.timeout.connect(lambda: finish('Desktop smoke test timed out'))
        timeout.start(30000)
        window.show()
        window.open_image(source)
        result = app.exec()
        timeout.stop()
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        report.write_text(json.dumps(state, indent=2) + '\n', encoding='utf-8')
        return result
