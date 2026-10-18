"""Offscreen tests of real context-sensitive controls, child processes and export."""
import os
import gc
from pathlib import Path
import time
import subprocess
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
pytest.importorskip('PySide6.QtWidgets')

from PIL import Image
from PySide6.QtCore import QCoreApplication, QEvent, QProcess
from PySide6.QtWidgets import QApplication

from retroimg.convert import convert_file
from retroimg.gui.controller import RenderController
from retroimg.gui.options import OptionsPanel
from retroimg.gui.window import MainWindow
from retroimg.profiles import PROFILES
from retroimg.ui_options import palette_choices, profile_modes


@pytest.fixture(scope='session')
def app():
    application = QApplication.instance() or QApplication([])
    yield application
    # Drain widget deletion while the QApplication is still alive. Qt-owned
    # children and Python signal closures must not outlive their application.
    application.closeAllWindows()
    for widget in application.topLevelWidgets():
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()


def drain_deletions():
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def wait_for(app, predicate, *, timeout=15):
    deadline = time.monotonic() + timeout
    while not predicate():
        app.processEvents()
        if time.monotonic() > deadline:
            pytest.fail('Timed out waiting for the desktop worker')
        time.sleep(.005)
    app.processEvents()


@pytest.fixture
def source(tmp_path):
    path = tmp_path / 'source ; $().png'
    image = Image.new('RGB', (13, 11))
    image.putdata([((x * 19) % 256, (y * 31) % 256, ((x + y) * 23) % 256)
                   for y in range(11) for x in range(13)])
    image.save(path)
    return path


@pytest.fixture
def panel(app):
    panel = OptionsPanel()
    yield panel
    panel.close()
    panel.deleteLater()
    drain_deletions()


CASES = [(profile.name, option, mode) for profile in PROFILES.values()
         for option, modes in (profile_modes(profile),) for mode in modes]


@pytest.mark.parametrize('name,option,mode', CASES)
def test_all_profile_mode_controls_match_shared_validation(panel, name, option, mode):
    profile = PROFILES[name]
    settings = dict(profile=name, palette=palette_choices(profile, mode, option)[0])
    if option:
        settings[option] = mode
    panel.set_settings(settings)
    actual = panel.settings()
    assert actual['profile'] == name
    if option:
        assert actual[option] == mode
    assert actual['palette'] in palette_choices(profile, mode, option)


def test_irrelevant_controls_hide_and_switching_clears_inapplicable_settings(panel):
    panel.set_settings(dict(profile='amiga-lores', amiga_mode='constrained', colours=16))
    machine = panel.forms['Machine']
    assert machine.isRowVisible(panel.fields['colours'])
    panel.fields['mode'].setCurrentIndex(panel.fields['mode'].findData('ham'))
    assert not machine.isRowVisible(panel.fields['colours'])
    assert panel.settings()['colours'] is None
    panel.set_settings(dict(profile='atari2600-ntsc', atari_mode='playfield', width=160, height=24))
    assert machine.isRowVisible(panel.fields['atari_row_height'])
    assert not panel.fields['width'].isEnabled()
    panel.fields['family'].setCurrentIndex(panel.fields['family'].findData('nes'))
    assert panel.settings()['palette'] == 'nes'
    assert panel.settings()['atari_row_height'] is None
    assert not machine.isRowVisible(panel.fields['atari_row_height'])
    assert panel.settings()['atari_mode'] == 'bitmap'


def test_hardware_defaults_follow_profile_but_explicit_preset_modes_survive(panel):
    assert panel.settings()['teletext_mode'] == 'mosaic'
    panel.set_settings(dict(profile='snes'))
    assert panel.settings()['snes_mode'] == 'tiles'
    panel.fields['family'].setCurrentIndex(panel.fields['family'].findData('c64'))
    assert panel.settings()['c64_mode'] == 'hires'
    assert panel.forms['Machine'].isRowVisible(panel.fields['mode'])
    panel.fields['profile'].setCurrentIndex(panel.fields['profile'].findData('c64-multicolour'))
    assert panel.settings()['c64_mode'] == 'multicolour'
    panel.set_settings(dict(profile='snes', snes_mode='bitmap', palette='c64'))
    assert panel.settings()['snes_mode'] == 'bitmap'
    assert panel.settings()['palette'] == 'c64'
    panel.set_settings(dict(profile='snes', snes_mode='indexed'))
    assert panel.settings()['snes_mode'] == 'indexed'


@pytest.mark.parametrize('size', [(980, 640), (1380, 850)])
def test_processing_and_status_messages_do_not_resize_previews(app, tmp_path, size):
    window = MainWindow(presets_dir=tmp_path)
    window.resize(*size)
    window.show()
    app.processEvents()
    original = window.original.view.geometry()
    result = window.result.view.geometry()
    status = window.status.geometry()
    try:
        for busy, message in ((True, 'Updating preview…'),
                              (False, 'Ready: 2390 × 1792 output; 320 × 224 logical pixels. '
                                      'Use 100% to inspect the display pattern.'),
                              (True, 'Updating preview…'),
                              (False, 'Could not update preview: ' + 'long error message ' * 30)):
            window._set_status(message)
            window._busy_changed(busy)
            app.processEvents()
            assert window.original.view.geometry() == original
            assert window.result.view.geometry() == result
            assert window.status.geometry() == status
            assert window.status.toolTip() == message
    finally:
        window.close()
        window.deleteLater()
        drain_deletions()


def test_bayer_effect_controls_and_minimum_scale_follow_context(panel):
    machine, display = panel.forms['Machine'], panel.forms['Display']
    assert not machine.isRowVisible(panel.fields['bayer_size'])
    panel.fields['dither'].setCurrentIndex(panel.fields['dither'].findData('bayer'))
    assert machine.isRowVisible(panel.fields['bayer_size'])
    assert panel.settings()['bayer_size'] == 4
    panel.auto_scale.setChecked(False)
    panel.fields['scale'].setValue(1)
    panel.fields['display_effect'].setCurrentIndex(panel.fields['display_effect'].findData('crt-aperture'))
    assert panel.fields['scale'].value() == 3
    assert display.isRowVisible(panel.fields['effect_strength'])
    assert not display.isRowVisible(panel.fields['bloom_radius'])
    panel.fields['bloom_strength'].setValue(.25)
    assert display.isRowVisible(panel.fields['bloom_radius'])
    panel.fields['display_effect'].setCurrentIndex(panel.fields['display_effect'].findData('none'))
    assert panel.settings()['effect_strength'] is None
    assert panel.settings()['bloom_strength'] == .25


def test_automatic_scale_tracks_machine_resolution_and_effect_requirements(panel):
    panel.set_settings(dict(profile='ega-640'))
    assert panel.auto_scale.isChecked()
    assert not panel.fields['scale'].isEnabled()
    assert panel.settings()['scale'] == 1
    assert '640 × 480' in panel.output_hint.text()
    panel.fields['family'].setCurrentIndex(panel.fields['family'].findData('gameboy'))
    assert panel.settings()['scale'] == 4
    panel.fields['family'].setCurrentIndex(panel.fields['family'].findData('spectrum'))
    assert panel.settings()['scale'] == 2
    panel.set_settings(dict(profile='ega-640'))
    panel.fields['display_effect'].setCurrentIndex(panel.fields['display_effect'].findData('crt-aperture'))
    assert panel.settings()['scale'] == 3
    panel.fields['display_effect'].setCurrentIndex(panel.fields['display_effect'].findData('none'))
    assert panel.settings()['scale'] == 1
    panel.custom.setChecked(True)
    panel.fields['width'].setValue(320)
    panel.fields['height'].setValue(200)
    assert panel.settings()['scale'] == 2
    panel.fields['height'].setValue(640)
    assert panel.settings()['scale'] == 1


def test_explicit_enlargement_survives_machine_changes_and_preset_loading(panel):
    panel.set_settings(dict(profile='gameboy', scale=6))
    assert not panel.auto_scale.isChecked()
    assert panel.fields['scale'].isEnabled()
    panel.fields['family'].setCurrentIndex(panel.fields['family'].findData('ega'))
    assert panel.settings()['scale'] == 6
    panel.auto_scale.setChecked(True)
    assert panel.settings()['scale'] == 2  # The family's first profile is ega-320.
    panel.auto_scale.setChecked(False)
    panel.fields['scale'].setValue(5)
    panel.fields['profile'].setCurrentIndex(panel.fields['profile'].findData('ega-640'))
    assert panel.settings()['scale'] == 5
    panel.set_settings(dict(profile='ega-640', scale=1))
    assert not panel.auto_scale.isChecked()
    assert panel.settings()['scale'] == 1


@pytest.mark.parametrize('profile,height', [('ega-640', 350), ('ega-640-200', 200)])
def test_automatic_ega_export_keeps_native_raster_without_excessive_enlargement(app, source, tmp_path, profile, height):
    window = MainWindow(presets_dir=tmp_path / 'presets')
    window.controller.timer.setInterval(0)
    window.options.set_settings(dict(profile=profile, ega_mode='constrained'))
    try:
        window.open_image(source)
        wait_for(app, lambda: window.export_button.isEnabled())
        assert f'640 × {height} logical pixels' in window.status.text()
        target = tmp_path / 'ega.png'
        window.export_to(target)
        with Image.open(target) as output:
            assert output.size == (640, 480)
        preset = tmp_path / 'enlargement.json'
        window.save_preset_to(preset)
        window.options.set_settings(dict(profile='gameboy'))
        assert window.options.settings()['scale'] == 4
        window.load_preset_path(preset)
        assert window.options.settings()['scale'] == 1
        assert not window.options.auto_scale.isChecked()
    finally:
        window.close()
        window.deleteLater()
        drain_deletions()


def test_mode_descriptions_match_the_selected_machine(panel):
    panel.set_settings(dict(profile='nes', nes_mode='attributes'))
    assert '16x16' in panel.mode_hint.text()
    assert 'ink/paper' not in panel.mode_hint.text()
    panel.set_settings(dict(profile='gameboy', gameboy_mode='tiles'))
    assert 'four luminance shades' in panel.mode_hint.text()


def test_preset_precision_and_custom_dimension_constraints_are_preserved(panel):
    panel.set_settings(dict(profile='nes', nes_mode='attributes', width=32, height=16, brightness=1.234567))
    assert panel.settings()['brightness'] == 1.234567
    assert panel.fields['width'].singleStep() == 16
    assert panel.settings()['width'] == 32
    panel.fields['width'].setValue(17)
    with pytest.raises(ValueError, match='divisible'):
        panel.settings()


def test_integer_preview_zoom_accounts_for_hidpi_physical_pixels(app, monkeypatch):
    from retroimg.gui.preview import ImagePane
    pane = ImagePane('Test')
    monkeypatch.setattr(pane.view, 'devicePixelRatioF', lambda: 2)
    pane.zoom_box.setCurrentIndex(pane.zoom_box.findData(1))
    assert pane.view.transform().m11() == .5
    pane.zoom_box.setCurrentIndex(pane.zoom_box.findData(4))
    assert pane.view.transform().m11() == 2
    pane.close()
    pane.deleteLater()
    drain_deletions()


@pytest.mark.parametrize('tab', ['Source', 'Display'])
def test_tab_reset_restores_defaults_once_and_preserves_other_settings(panel, tab):
    from PySide6.QtTest import QSignalSpy
    panel.set_settings(dict(profile='ega-640', ega_mode='constrained', width=320, height=200,
                            dither='bayer', bayer_size=2, brightness=1.7, contrast=.8,
                            saturation=2, hue_shift=42, red_gain=.4, green_gain=1.2, blue_gain=2,
                            scale=6, display_effect='crt-aperture', effect_strength=.8,
                            rf_strength=.7, chromatic_strength=.6, bloom_strength=.5,
                            bloom_radius=3, display_brightness=1.5))
    before = panel.settings()
    changed = QSignalSpy(panel.changed)
    panel.reset_buttons[tab].click()
    actual = panel.settings()
    assert changed.count() == 1
    own_keys = {key for key, widget in panel.fields.items() if panel.forms[tab].indexOf(widget) >= 0}
    for key in actual:
        if key not in own_keys:
            assert actual[key] == before[key], key
        elif key != 'scale':
            assert actual[key] == panel.defaults[key], key
    if tab == 'Display':
        assert panel.auto_scale.isChecked()
        assert actual['scale'] == 2
        assert not panel.forms['Display'].isRowVisible(panel.fields['effect_strength'])
        assert not panel.forms['Display'].isRowVisible(panel.fields['bloom_radius'])
        panel.fields['display_effect'].setCurrentIndex(panel.fields['display_effect'].findData('scanlines'))
        assert panel.settings()['effect_strength'] == .35
    else:
        assert not panel.auto_scale.isChecked()


@pytest.mark.parametrize('dpr', [1, 2])
def test_wheel_zoom_preserves_pointer_and_updates_only_its_panel(app, monkeypatch, dpr):
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QImage, QWheelEvent
    from retroimg.gui.preview import ImagePane
    pane, other = ImagePane('Original'), ImagePane('Result')
    monkeypatch.setattr(pane.view, 'devicePixelRatioF', lambda: dpr)
    pane.resize(700, 500)
    pane.show()
    image = QImage(2400, 1800, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    pane.set_image(image)
    other.set_image(image)
    app.processEvents()

    def wheel(delta, *, pixels=False):
        position = QPointF(pane.view.viewport().rect().center()) + QPointF(35, 20)
        event = QWheelEvent(position, QPointF(pane.view.viewport().mapToGlobal(position.toPoint())),
                            QPoint(0, delta) if pixels else QPoint(),
                            QPoint() if pixels else QPoint(0, delta), Qt.MouseButton.NoButton,
                            Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
        QApplication.sendEvent(pane.view.viewport(), event)
        app.processEvents()
        assert event.isAccepted()

    try:
        fit = pane.view.transform().m11()
        wheel(120)
        assert pane.view.transform().m11() == pytest.approx(fit * 1.25)
        assert pane.view.zoom == pane.zoom_box.currentData()
        assert other.view.zoom is None
        pane.zoom_box.setCurrentIndex(pane.zoom_box.findData(1))
        app.processEvents()
        point = pane.view.viewport().rect().center() + QPoint(35, 20)
        before = pane.view.mapToScene(point)
        wheel(120)
        after = pane.view.mapToScene(point)
        assert abs(before.x() - after.x()) < 4
        assert abs(before.y() - after.y()) < 4
        assert pane.view.zoom == pytest.approx(1.25)
        wheel(-120)
        assert pane.view.zoom == pytest.approx(1)
        wheel(60, pixels=True)
        assert pane.view.zoom == pytest.approx(1.25 ** .5)
        assert pane.zoom_box.count() <= 6
        for _ in range(3):
            wheel(12000)
        assert pane.view.zoom == 32
        for _ in range(3):
            wheel(-12000)
        assert pane.view.zoom == .01
        pane.set_image(image)
        assert pane.view.zoom == .01
        pane.zoom_box.setCurrentIndex(0)
        assert pane.view.zoom is None
        assert pane.view.transform().m11() == pytest.approx(fit)
    finally:
        for widget in (pane, other):
            widget.close()
            widget.deleteLater()
        drain_deletions()


def test_desktop_launcher_closes_cleanly_with_widgets_and_signals():
    script = '''
from PySide6.QtCore import QTimer
from retroimg.gui.window import MainWindow
from retroimg.gui import main
original = MainWindow.show
def show(self):
    original(self)
    QTimer.singleShot(25, self.close)
MainWindow.show = show
raise SystemExit(main([]))
'''
    subprocess.run([sys.executable, '-X', 'faulthandler', '-c', script],
                   check=True, capture_output=True, text=True, timeout=15)


def test_controller_discards_superseded_results_and_cancels(app, source):
    controller = RenderController(debounce_ms=0)
    ready, failed = [], []
    controller.ready.connect(ready.append)
    controller.failed.connect(failed.append)
    options = dict(profile='gameboy', gameboy_mode='tiles', width=8, height=8, scale=3)
    try:
        controller.submit(source, kind='retro', settings=options)
        wait_for(app, lambda: controller.process.state() == QProcess.ProcessState.Running)
        controller.submit(source, kind='retro', settings=dict(options, bloom_strength=.25))
        wanted = controller.revision
        wait_for(app, lambda: bool(ready))
        assert [result['revision'] for result in ready] == [wanted]
        assert not failed
        controller.submit(source, kind='retro', settings=dict(options, rf_strength=.85))
        wait_for(app, lambda: controller.process.state() == QProcess.ProcessState.Running)
        controller.cancel()
        wait_for(app, lambda: controller.process.state() == QProcess.ProcessState.NotRunning)
        assert len(ready) == 1 and not failed
    finally:
        controller.close()
        controller.deleteLater()
        drain_deletions()


def test_controller_recovers_after_an_invalid_source(app, source):
    controller = RenderController(debounce_ms=0)
    ready, errors = [], []
    controller.ready.connect(ready.append)
    controller.failed.connect(errors.append)
    try:
        controller.submit(source.with_name('missing.png'), kind='pixelate', block_size=4)
        wait_for(app, lambda: bool(errors))
        controller.submit(source, kind='pixelate', block_size=4)
        wait_for(app, lambda: bool(ready))
        assert ready[0]['size'] == [13, 11]
    finally:
        controller.close()
        controller.deleteLater()
        drain_deletions()


def test_window_exports_full_pixels_preserves_source_and_shares_presets(app, source, tmp_path):
    window = MainWindow(presets_dir=tmp_path / 'presets')
    window.controller.timer.setInterval(0)
    options = dict(profile='gameboy', gameboy_mode='tiles', width=8, height=8, scale=3)
    window.options.set_settings(options)
    before = source.read_bytes()
    try:
        window.open_image(source)
        wait_for(app, lambda: window.export_button.isEnabled())
        window.result.zoom_box.setCurrentIndex(window.result.zoom_box.findData(8))
        assert window.result.view.transform().m11() == 8
        exported = tmp_path / 'export.png'
        window.export_to(exported)
        expected = tmp_path / 'cli.png'
        convert_file(source, expected, profile_name='gameboy', gameboy_mode='tiles', width=8, height=8, scale=3)
        with Image.open(exported) as actual, Image.open(expected) as reference:
            assert actual.size == reference.size == (24, 24)
            assert actual.tobytes() == reference.tobytes()
        with pytest.raises(ValueError, match='source image'):
            window.export_to(source, replace=True)
        with pytest.raises(FileExistsError):
            window.export_to(exported)
        assert source.read_bytes() == before
        preset = tmp_path / 'shared.json'
        window.save_preset_to(preset)
        window.options.fields['brightness'].setValue(.7)
        assert not window.export_button.isEnabled()
        with pytest.raises(ValueError, match='current preview'):
            window.export_to(tmp_path / 'stale.png')
        window.load_preset_path(preset)
        assert window.options.settings()['brightness'] == 1
        wait_for(app, lambda: window.export_button.isEnabled())
        window.options.kind.setCurrentIndex(window.options.kind.findData('pixelate'))
        assert window.options.tabs.isHidden() and not window.options.pixelate_panel.isHidden()
        assert not window.save_preset_button.isEnabled()
        wait_for(app, lambda: window.export_button.isEnabled())
        window.export_to(tmp_path / 'pixelate.png')
        with Image.open(tmp_path / 'pixelate.png') as output:
            assert output.size == (13, 11)
    finally:
        window.close()
        window.deleteLater()
        drain_deletions()
