"""Context-sensitive desktop controls using the existing mode/palette registry."""
from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt, Signal, QSignalBlocker
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel,
    QSlider, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from retroimg.cli import build_parser
from retroimg.conversion_modes import COLOUR_COUNT_QUANTIZERS
from retroimg.display_effects import DISPLAY_EFFECTS, MINIMUM_EFFECT_SCALES
from retroimg.ordered import BAYER_SIZES, DITHER_MODES
from retroimg.profiles import PROFILES
from retroimg.settings import CELL_DIMENSIONS, default_settings, normalize_settings
from retroimg.targets.amiga import AMIGA_COLOUR_LIMITS
from retroimg.ui_options import (
    FAMILY_LABELS, mode_description, mode_label, palette_choices, profile_families,
    profile_modes, preferred_mode, suggested_scale,
)


class NumberControl(QWidget):
    changed = Signal()

    def __init__(self, low: float, high: float, value: float, step: float = .01):
        super().__init__()
        self.low, self.high, self.step = low, high, step
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, round((high - low) / step))
        self.spin = QDoubleSpinBox()
        self.spin.setDecimals(2)
        self.spin.setRange(low, 100 if high == 4 else high)
        self.spin.setSingleStep(step)
        self.spin.setKeyboardTracking(False)
        self.spin.setMinimumWidth(76)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.spin)
        self.slider.valueChanged.connect(lambda position: self.spin.setValue(low + position * step))
        self.spin.valueChanged.connect(self._changed)
        self.setValue(value)

    def _changed(self):
        with QSignalBlocker(self.slider):
            self.slider.setValue(round((self.spin.value() - self.low) / self.step))
        self.changed.emit()

    def value(self):
        return self.spin.value()

    def setValue(self, value):
        self.spin.setDecimals(max(2, min(16, -Decimal(str(value)).as_tuple().exponent)))
        self.spin.setRange(min(self.spin.minimum(), value), max(self.spin.maximum(), value))
        self.spin.setValue(value)
        self._changed()


class OptionsPanel(QWidget):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.defaults = default_settings(build_parser())
        self._updating = True
        self.fields: dict[str, QWidget] = {}
        self.forms: dict[str, QFormLayout] = {}
        self.families = profile_families()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.kind = QComboBox()
        self.kind.addItem('Retro conversion', 'retro')
        self.kind.addItem('Pixelate original colours', 'pixelate')
        layout.addWidget(self.kind)
        self.pixelate_panel = QWidget()
        pixelate_form = QFormLayout(self.pixelate_panel)
        self.block_size = self._spin(1, 1000000, 8)
        pixelate_form.addRow('Block size', self.block_size)
        hint = QLabel('Original colours and image dimensions are preserved. Block size is measured in source pixels.')
        hint.setWordWrap(True)
        pixelate_form.addRow(hint)
        layout.addWidget(self.pixelate_panel)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        for title in ('Machine', 'Source', 'Display'):
            panel = QWidget()
            form = QFormLayout(panel)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
            form.setVerticalSpacing(12)
            self.forms[title] = form
            self.tabs.addTab(panel, title)

        self._combo('family', 'Machine', 'Machine', [(FAMILY_LABELS.get(k, k), k) for k in self.families])
        self._combo('profile', 'Profile', 'Machine', [])
        self._combo('mode', 'Conversion mode', 'Machine', [])
        self.mode_hint = QLabel()
        self.mode_hint.setWordWrap(True)
        self.forms['Machine'].addRow(self.mode_hint)
        self._combo('palette', 'Palette', 'Machine', [])
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.forms['Machine'].addRow(self.description)
        self._combo('colours', 'Screen colours', 'Machine', [])
        self._field('atari_row_height', 'Band height', 'Machine', self._spin(1, 1024, 2))
        self.custom = QCheckBox('Custom logical resolution')
        self.forms['Machine'].addRow(self.custom)
        self._field('width', 'Logical width', 'Machine', self._spin(1, 16384, 80))
        self._field('height', 'Logical height', 'Machine', self._spin(1, 16384, 75))
        self.geometry_hint = QLabel()
        self.geometry_hint.setWordWrap(True)
        self.forms['Machine'].addRow(self.geometry_hint)
        self._combo('fit', 'Image fitting', 'Machine', [(name.title(), name) for name in ('cover', 'contain', 'stretch')])
        self._combo('dither', 'Dithering', 'Machine', [(name, name) for name in DITHER_MODES])
        self._combo('bayer_size', 'Bayer matrix', 'Machine', [(f'{n} × {n}', n) for n in BAYER_SIZES])

        self.forms['Source'].addRow(QLabel('Adjustments before palette conversion'))
        for key, label in (('brightness', 'Brightness'), ('contrast', 'Contrast'), ('saturation', 'Saturation'),
                           ('hue_shift', 'Hue (degrees)'), ('red_gain', 'Red gain'),
                           ('green_gain', 'Green gain'), ('blue_gain', 'Blue gain')):
            low, high, step = ((-180, 180, 1) if key == 'hue_shift' else
                               (.01, 4, .01) if key == 'saturation' else (0, 4, .05))
            self._field(key, label, 'Source', NumberControl(low, high, self.defaults[key], step))
        self.auto_scale = QCheckBox('Automatic enlargement')
        self.auto_scale.setToolTip('Choose an integer enlargement for roughly 640 pixels on the longest edge. '
                                  'LCD and CRT treatments require at least 3×.')
        self.forms['Display'].addRow(self.auto_scale)
        self._field('scale', 'Output enlargement', 'Display', self._spin(1, 64, 1))
        self.output_hint = QLabel()
        self.output_hint.setWordWrap(True)
        self.forms['Display'].addRow(self.output_hint)
        self._field('rf_strength', 'RF colour bleed', 'Display', NumberControl(0, 1, 0))
        self._field('chromatic_strength', 'Chromatic aberration', 'Display', NumberControl(0, 1, 0))
        self._combo('display_effect', 'Display treatment', 'Display', [(name, name) for name in DISPLAY_EFFECTS])
        self._field('effect_strength', 'Treatment strength', 'Display', NumberControl(0, 1, .35))
        self._field('bloom_strength', 'Bloom strength', 'Display', NumberControl(0, 1, 0))
        self._field('bloom_radius', 'Bloom radius', 'Display', NumberControl(.25, 8, 1, .05))
        self.fields['bloom_radius'].setToolTip('Gaussian spread in logical pixel widths.')
        self._field('display_brightness', 'Display brightness', 'Display', NumberControl(0, 4, 1, .05))
        display_hint = QLabel('Order: RF → chromatic aberration → display treatment → bloom → display brightness.\n'
                              'These effects work in full RGB after conversion.')
        display_hint.setWordWrap(True)
        self.forms['Display'].addRow(display_hint)
        self._updating = False
        self.fields['family'].currentIndexChanged.connect(self._family_changed)
        self.fields['profile'].currentIndexChanged.connect(self._profile_changed)
        self.fields['mode'].currentIndexChanged.connect(self._mode_changed)
        self.kind.currentIndexChanged.connect(self._context_changed)
        self.custom.toggled.connect(self._context_changed)
        self.auto_scale.toggled.connect(self._context_changed)
        self.block_size.valueChanged.connect(self._emit_change)
        self.set_settings({})

    @staticmethod
    def _spin(low, high, value):
        spin = QSpinBox()
        spin.setRange(low, high)
        spin.setValue(value)
        spin.setKeyboardTracking(False)
        return spin

    def _field(self, key, label, tab, widget):
        self.fields[key] = widget
        self.forms[tab].addRow(label, widget)
        if isinstance(widget, NumberControl):
            widget.changed.connect(self._context_changed)
        elif isinstance(widget, QSpinBox):
            widget.valueChanged.connect(self._geometry_changed if key in ('width', 'height', 'scale')
                                        else self._emit_change)
        return widget

    def _combo(self, key, label, tab, entries):
        widget = self._field(key, label, tab, QComboBox())
        self._fill(widget, entries)
        if key not in ('family', 'profile', 'mode'):
            widget.currentIndexChanged.connect(self._context_changed)

    @staticmethod
    def _fill(widget, entries, preferred=None):
        with QSignalBlocker(widget):
            widget.clear()
            for label, value in entries:
                widget.addItem(label, value)
            index = widget.findData(preferred)
            widget.setCurrentIndex(max(0, index))

    def _value(self, key):
        widget = self.fields[key]
        return widget.currentData() if isinstance(widget, QComboBox) else widget.value()

    def _family_changed(self):
        if self._updating:
            return
        family = self._value('family')
        self._fill(self.fields['profile'], [(p.name, p.name) for p in self.families[family]])
        self._profile_changed()

    def _profile_changed(self):
        if self._updating:
            return
        profile = PROFILES[self._value('profile')]
        option, modes = profile_modes(profile)
        self._fill(self.fields['mode'], [(mode_label(mode), mode) for mode in modes], preferred_mode(modes))
        choices = palette_choices(profile, self._value('mode'), option)
        self._fill(self.fields['palette'], [(name, name) for name in choices], profile.default_palette)
        for key, value in (('width', profile.geometry.width), ('height', profile.geometry.height)):
            with QSignalBlocker(self.fields[key]):
                self.fields[key].setValue(value)
        self._mode_changed()

    def _mode_changed(self):
        if self._updating:
            return
        profile = PROFILES[self._value('profile')]
        option, _ = profile_modes(profile)
        choices = palette_choices(profile, self._value('mode'), option)
        preferred = self._value('palette')
        self._fill(self.fields['palette'], [(name, name) for name in choices], preferred)
        if (profile.constraint_model, self._value('mode')) in COLOUR_COUNT_QUANTIZERS:
            limit = AMIGA_COLOUR_LIMITS[profile.constraint_model.removeprefix('amiga-')]
            counts = [2**n for n in range(1, limit.bit_length())]
            old = self._value('colours')
            self._fill(self.fields['colours'], [(str(n), n) for n in counts], old if old in counts else limit)
        self._context_changed()

    def _context_changed(self):
        if self._updating:
            return
        self._updating = True
        pixelate = self.kind.currentData() == 'pixelate'
        self.pixelate_panel.setVisible(pixelate)
        self.tabs.setVisible(not pixelate)
        profile = PROFILES[self._value('profile')]
        mode = self._value('mode')
        option, modes = profile_modes(profile)
        self.mode_hint.setText(mode_description(option, mode))
        self.fields['mode'].setToolTip(self.mode_hint.text())
        form = self.forms['Machine']
        form.setRowVisible(self.fields['profile'], len(self.families[self._value('family')]) > 1)
        form.setRowVisible(self.fields['mode'], len(modes) > 1)
        form.setRowVisible(self.fields['palette'], self.fields['palette'].count() > 1)
        form.setRowVisible(self.fields['colours'], (profile.constraint_model, mode) in COLOUR_COUNT_QUANTIZERS)
        form.setRowVisible(self.fields['atari_row_height'], option == 'atari_mode' and mode != 'bitmap')
        multiples = CELL_DIMENSIONS.get(profile.constraint_model, (1, 1)) if mode != 'bitmap' else (1, 1)
        fixed = option == 'atari_mode' and mode != 'bitmap'
        for key, step in zip(('width', 'height'), multiples):
            widget = self.fields[key]
            widget.setSingleStep(step)
            if widget.value() % step:
                widget.setValue(max(step, widget.value() // step * step))
            form.setRowVisible(widget, self.custom.isChecked())
        self.fields['width'].setEnabled(not fixed)
        if fixed:
            self.fields['width'].setValue(160)
        self.description.setText(profile.description + f'\nPalette: {self._value("palette")}')
        self.geometry_hint.setText(f'Native: {profile.geometry.width} × {profile.geometry.height}. '
                                   + (f'Custom dimensions use multiples of {multiples[0]} × {multiples[1]}.' if mode != 'bitmap' else ''))
        form.setRowVisible(self.fields['bayer_size'], self._value('dither') == 'bayer')
        display = self._value('display_effect')
        self._update_scale()
        self.forms['Display'].setRowVisible(self.fields['effect_strength'], display != 'none')
        self.forms['Display'].setRowVisible(self.fields['bloom_radius'], self._value('bloom_strength') > 0)
        self._updating = False
        self.changed.emit()

    def _update_scale(self):
        profile = PROFILES[self._value('profile')]
        width, height = ((self._value('width'), self._value('height')) if self.custom.isChecked()
                         else (profile.geometry.width, profile.geometry.height))
        scale = self.fields['scale']
        minimum = MINIMUM_EFFECT_SCALES[self._value('display_effect')]
        scale.setMinimum(minimum)
        scale.setEnabled(not self.auto_scale.isChecked())
        if self.auto_scale.isChecked():
            scale.setValue(suggested_scale(profile, width, height, minimum=minimum))
        aspect = profile.geometry.pixel_aspect if profile.aspect_correct_preview else 1
        output_width = max(1, round(width * scale.value() * max(1, aspect)))
        output_height = max(1, round(height * scale.value() * max(1, 1 / aspect)))
        self.output_hint.setText(f'Output: {output_width} × {output_height} pixels.')

    def _geometry_changed(self):
        if not self._updating:
            self._updating = True
            self._update_scale()
            self._updating = False
            self.changed.emit()

    def _emit_change(self):
        if not self._updating:
            self.changed.emit()

    def settings(self) -> dict:
        values = {key: self._value(key) for key in self.fields if key not in ('family', 'mode', 'width', 'height', 'colours', 'atari_row_height')}
        profile = PROFILES[values['profile']]
        option, _ = profile_modes(profile)
        mode = self._value('mode')
        if option is not None:
            values[option] = mode
        if self.custom.isChecked():
            values.update(width=self._value('width'), height=self._value('height'))
        if (profile.constraint_model, mode) in COLOUR_COUNT_QUANTIZERS:
            values['colours'] = self._value('colours')
        if option == 'atari_mode' and mode != 'bitmap':
            values['atari_row_height'] = self._value('atari_row_height')
        if values['dither'] != 'bayer':
            values['bayer_size'] = None
        if values['display_effect'] == 'none':
            values['effect_strength'] = None
        return normalize_settings(values, self.defaults)

    def set_settings(self, raw: dict) -> None:
        requested = dict(raw)
        profile = PROFILES.get(requested.get('profile', self.defaults['profile']))
        if profile is not None:
            option, modes = profile_modes(profile)
            if option is not None and option not in requested:
                requested[option] = preferred_mode(modes)
        values = normalize_settings(requested, self.defaults)
        self._updating = True
        self.auto_scale.setChecked('scale' not in raw)
        profile = PROFILES[values['profile']]
        family = profile.name.split('-', 1)[0]
        self.fields['family'].setCurrentIndex(self.fields['family'].findData(family))
        self._fill(self.fields['profile'], [(p.name, p.name) for p in self.families[family]], profile.name)
        option, modes = profile_modes(profile)
        mode = values.get(option, 'bitmap')
        self._fill(self.fields['mode'], [(mode_label(m), m) for m in modes], mode)
        self._fill(self.fields['palette'], [(name, name) for name in palette_choices(profile, mode, option)], values['palette'])
        limit = AMIGA_COLOUR_LIMITS.get(profile.constraint_model.removeprefix('amiga-'), 32)
        self._fill(self.fields['colours'], [(str(2**n), 2**n) for n in range(1, limit.bit_length())], values.get('colours') or limit)
        self.custom.setChecked(values['width'] is not None)
        for key, widget in self.fields.items():
            if key in ('family', 'profile', 'mode', 'palette', 'colours'):
                continue
            value = values.get(key)
            if value is None:
                value = {'width': profile.geometry.width, 'height': profile.geometry.height,
                         'atari_row_height': 2, 'effect_strength': .35, 'bayer_size': 4}.get(key)
            if isinstance(widget, QComboBox):
                widget.setCurrentIndex(widget.findData(value))
            elif isinstance(widget, QSpinBox):
                widget.setMinimum(1)
                widget.setMaximum(max(widget.maximum(), value))
                widget.setValue(value)
            else:
                widget.setValue(value)
        self._updating = False
        self._context_changed()
