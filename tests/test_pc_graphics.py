"""CGA fixed graphics palettes and EGA register/display colour rules."""
from dataclasses import replace

import pytest
from PIL import Image

from retroimg.cli import build_parser
from retroimg.convert import convert_file
from retroimg.guided import palette_choices
from retroimg.palettes import get_palette
from retroimg.palettes.cga import CGA, CGA_PALETTES, CGA_MONO
from retroimg.palettes.ega import EGA, EGA_RGB, EGA_DEFAULT
from retroimg.profiles import get_profile
from retroimg.render import render_indexed
from retroimg.settings import default_settings, normalize_settings, merge_settings
from retroimg.targets.cga import optimise_cga, rasterize_cga
from retroimg.targets.ega import encode_colour, decode_colour, optimise_ega, rasterize_ega
from examples.generate_gallery import check_constraints


def source():
    image = Image.new('RGB', (16, 24))
    image.putdata([((x*23+y*7)%256, (x*7+y*41)%256, (x*17+y*19)%256)
                   for y in range(24) for x in range(16)])
    return image


@pytest.mark.parametrize('name,rgb,register', [
    ('cga-pal0-low', ((0,0,0),(0,170,0),(170,0,0),(170,85,0)), 0x00),
    ('cga-pal0-high', ((0,0,0),(85,255,85),(255,85,85),(255,255,85)), 0x10),
    ('cga-pal1-low', ((0,0,0),(0,170,170),(170,0,170),(170,170,170)), 0x20),
    ('cga-pal1-high', ((0,0,0),(85,255,255),(255,85,255),(255,255,255)), 0x30),
])
def test_cga_palette_codes_and_brown(name, rgb, register):
    palette = get_palette(name)
    assert palette.rgb_values() == rgb
    image = Image.new('RGB', (4, 1)); image.putdata(rgb)
    model = optimise_cga(image, palette)
    assert model.colour_select == register
    assert model.pixels == ((0,1,2,3),)
    assert render_indexed(rasterize_cga(model)).tobytes() == image.tobytes()


@pytest.mark.parametrize('dither,size', [('none',4),('floyd-steinberg',4),('bayer',2),('bayer',4),('bayer',8)])
def test_cga_modes_keep_fixed_palettes(dither,size):
    for palette in (*CGA_PALETTES.values(), CGA_MONO):
        resolution = 640 if palette == CGA_MONO else 320
        model = optimise_cga(source(), palette, dither, resolution=resolution, bayer_size=size)
        assert model == optimise_cga(source(), palette, dither, resolution=resolution, bayer_size=size)
        output = rasterize_cga(model)
        check_constraints(output,dict(cga_mode='constrained',profile_name=f'cga-{resolution}',palette_name=palette.name))
        assert len(render_indexed(output).getcolors()) <= (2 if resolution==640 else 4)


def test_ega_register_encoding_and_classic_palette():
    assert encode_colour((170,85,0)) == 0x14  # Brown is not dark yellow (0x06).
    assert decode_colour(0x06) == (170,170,0)
    assert tuple(encode_colour(rgb) for rgb in EGA_DEFAULT.rgb_values()) == (
        0,1,2,3,4,5,20,7,56,57,58,59,60,61,62,63)
    for value in range(64):
        assert encode_colour(decode_colour(value)) == value
    for value in (-1,64,True):
        with pytest.raises(ValueError): decode_colour(value)


@pytest.mark.parametrize('scanlines,palette', [(200,EGA_DEFAULT),(350,EGA_DEFAULT),(350,EGA)])
@pytest.mark.parametrize('dither,size', [('none',4),('floyd-steinberg',4),('bayer',2),('bayer',4),('bayer',8)])
def test_ega_screens_keep_limits_and_are_deterministic(scanlines,palette,dither,size):
    model = optimise_ega(source(),palette,dither,scanlines=scanlines,bayer_size=size)
    assert model == optimise_ega(source(),palette,dither,scanlines=scanlines,bayer_size=size)
    output = rasterize_ega(model)
    assert len(model.registers)<=16
    assert all(EGA_RGB.snap(rgb)==rgb for rgb in output.palette.rgb_values())
    check_constraints(output,dict(ega_mode='constrained',profile_name='ega-320' if scanlines==200 else 'ega-640'))
    assert render_indexed(output).mode=='RGB'


def test_ega_350_line_selection_uses_colours_beyond_rgbi():
    colour=(85,0,0)
    assert colour not in EGA_DEFAULT.rgb_values()
    image=Image.new('RGB',(8,8),colour)
    model=optimise_ega(image,EGA)
    assert render_indexed(rasterize_ega(model)).getcolors()==[(64,colour)]
    with pytest.raises(ValueError,match='RGBI'):
        replace(model,scanlines=200)
    with pytest.raises(ValueError,match='palette'):
        optimise_ega(image,EGA,scanlines=200)


def test_models_reject_invalid_pixels_and_registers():
    cga=optimise_cga(source(),CGA_PALETTES['cga-pal1-high'])
    for change in ({'resolution':1},{'colour_select':0},{'width':0},{'pixels':((4,)*16,)*24}):
        with pytest.raises(ValueError): replace(cga,**change)
    ega=optimise_ega(source(),EGA)
    for change in ({'scanlines':1},{'registers':()},{'registers':(64,)},
                   {'registers':(0,)*17},{'pixels':((16,)*16,)*24}):
        with pytest.raises(ValueError): replace(ega,**change)


def test_guided_and_preset_palette_restrictions_follow_resolution():
    defaults=default_settings(build_parser())
    for name,flag,allowed in (
        ('cga-320','cga_mode',set(CGA_PALETTES)),('cga-640','cga_mode',{'cga-mono'}),
        ('ega-320','ega_mode',{'ega-default'}),('ega-640-200','ega_mode',{'ega-default'}),
        ('ega-640','ega_mode',{'ega','ega-default'}),
    ):
        assert set(palette_choices(get_profile(name),'constrained',flag))==allowed
        for palette in allowed:
            values=normalize_settings(dict(profile=name,palette=palette,**{flag:'constrained'}),defaults)
            assert values['palette']==palette
            reset=merge_settings(values,dict(profile='teletext'),defaults)
            assert reset[flag]=='bitmap'
        with pytest.raises(ValueError,match='palette'):
            normalize_settings(dict(profile=name,palette='c64',**{flag:'constrained'}),defaults)


@pytest.mark.parametrize('flag', ['cga_mode','ega_mode'])
def test_incompatible_modes_fail_before_opening_input(tmp_path,flag):
    with pytest.raises(ValueError,match='only valid'):
        convert_file(tmp_path/'missing',tmp_path/'out.png',**{flag:'constrained'})


def test_unrestricted_palette_swaps_remain_available(tmp_path):
    path=tmp_path/'source.png'; source().save(path)
    for profile,palette in (('cga-320','cga'),('ega-320','ega')):
        actual=convert_file(path,tmp_path/'out.png',profile_name=profile,palette_name=palette,width=16,height=24,scale=1)
        assert actual.palette==get_palette(palette)
