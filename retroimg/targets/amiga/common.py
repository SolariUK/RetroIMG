"""Validation shared by six-bit Amiga graphics representations."""


def validate_screen(width: int, height: int, registers: tuple[int, ...],
                    codes: tuple[tuple[int, ...], ...], slots: int) -> None:
    """Shared validation of fixed register tables and six-bit logical pixels."""
    if any(type(size) is not int or size <= 0 for size in (width, height)):
        raise ValueError('Amiga dimensions must be positive integers')
    if len(registers) != slots:
        raise ValueError(f'Amiga register table must contain exactly {slots} entries')
    if any(type(value) is not int or not 0 <= value <= 0xfff for value in registers):
        raise ValueError('Amiga register colours must be integers in 0x000..0xfff')
    if len(codes) != height or any(len(row) != width for row in codes):
        raise ValueError('Amiga code grid does not match dimensions')
    if any(type(code) is not int or not 0 <= code < 64 for row in codes for code in row):
        raise ValueError('Amiga pixel codes must be integers in 0..63')

