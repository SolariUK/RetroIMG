"""The base installation can convert and run the guide without completion."""
import subprocess
import sys

from PIL import Image


def test_convert_and_guided_without_prompt_toolkit(tmp_path):
    source, output = tmp_path / 'source image.png', tmp_path / 'converted.png'
    Image.new('RGB', (4, 4), (50, 150, 200)).save(source)
    script = '''
import builtins
import importlib.abc
import sys

class NoCompletion(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'prompt_toolkit' or fullname.startswith('prompt_toolkit.'):
            raise ModuleNotFoundError('Completion extra is not installed', name=fullname)

sys.meta_path.insert(0, NoCompletion())
from retroimg.cli import main
source, output = sys.argv[1:]
main(['convert', source, output])
answers = iter([source, output])
def read(message):
    print(message)
    if message.startswith(('Input image', 'Output image')):
        return next(answers)
    return ''
builtins.input = read
main(['guided', '--print-only'])
assert not any(name.startswith('prompt_toolkit') for name in sys.modules)
'''
    result = subprocess.run([sys.executable, '-c', script, str(source), str(output)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert 'Input image path: ' in result.stdout
    assert 'Output image path (PNG recommended)' in result.stdout
    assert 'Tab to complete' not in result.stdout
    assert 'Equivalent command' in result.stdout
    with Image.open(output) as converted:
        converted.verify()
