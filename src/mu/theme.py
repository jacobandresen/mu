"""base16 colour scheme picker and applier."""

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Scheme:
    name: str = ''
    author: str = ''
    system: str = ''
    slug: str = ''
    variant: str = ''
    palette: dict = field(default_factory=dict)  # '00'–'0f' → 6-digit hex


_SLOT_RE = re.compile(r'(?i)base([0-9a-f]{2})\s*:\s*"?#?([0-9a-f]{6})')
_PALETTE_HEADER_RE = re.compile(r'^palette\s*:')
_NON_INDENT_RE = re.compile(r'^\S')


def parse_scheme(path) -> Scheme | None:
    s = Scheme()
    in_palette = False
    try:
        with open(path) as f:
            for line in f:
                line = line.rstrip('\n')
                if _PALETTE_HEADER_RE.match(line):
                    in_palette = True
                elif in_palette and _NON_INDENT_RE.match(line):
                    in_palette = False
                if not in_palette:
                    for fname in ('name', 'author', 'system', 'slug', 'variant'):
                        m = re.match(rf'(?i)^{fname}\s*:\s*(.+)$', line)
                        if m:
                            setattr(s, fname, m.group(1).strip().strip('"').strip("'"))
                m = _SLOT_RE.search(line)
                if m:
                    s.palette[m.group(1).lower()] = m.group(2).lower()
    except OSError:
        return None
    if not s.name and not s.palette:
        return None
    return s


def list_schemes(base16_dir) -> list[tuple[str, str]]:
    items = []
    for p in Path(base16_dir).rglob('*.yaml'):
        s = parse_scheme(p)
        if s and s.name:
            items.append((s.name, str(p)))
    items.sort(key=lambda x: x[0].lower())
    return items


def _hex_to_rgb(hex6: str) -> tuple[int, int, int]:
    if len(hex6) != 6:
        return 0, 0, 0
    return int(hex6[0:2], 16), int(hex6[2:4], 16), int(hex6[4:6], 16)


def _bg_block(hex6: str) -> str:
    if not hex6:
        return '   '
    r, g, b = _hex_to_rgb(hex6)
    return f'\033[48;2;{r};{g};{b}m   \033[0m'


def _fg_on_bg(fghex: str, bghex: str) -> str:
    fr, fg, fb = _hex_to_rgb(fghex)
    br, bg, bb = _hex_to_rgb(bghex)
    return f'\033[38;2;{fr};{fg};{fb}m\033[48;2;{br};{bg};{bb}m {fghex} \033[0m'


def preview(s: Scheme) -> None:
    labels_lo = ['Background', 'Alt Bg', 'Selection', 'Comments',
                 'Dark Fg', 'Foreground', 'Light Fg', 'Light Bg']
    labels_hi = ['Red', 'Orange', 'Yellow', 'Green', 'Cyan', 'Blue', 'Magenta', 'Brown']

    print()
    print(f'  \033[1m{s.name}\033[0m')
    if s.author:
        print(f'  by {s.author}')
    print()

    print('  ', end='')
    for i in range(8):
        print(_bg_block(s.palette.get(f'{i:02x}', '')), end='')
    print('\n  ', end='')
    for lbl in labels_lo:
        print(f' {lbl[0]} ', end='')
    print('\n')

    print('  ', end='')
    for i in range(8, 16):
        print(_bg_block(s.palette.get(f'{i:02x}', '')), end='')
    print('\n  ', end='')
    for lbl in labels_hi:
        print(f' {lbl[0]} ', end='')
    print('\n')

    bg = s.palette.get('00', '')
    if bg:
        print('  Accents on background:\n  ', end='')
        for i in range(8, 16):
            hex6 = s.palette.get(f'{i:02x}', '')
            print(_fg_on_bg(hex6, bg) if hex6 else '       ', end='')
        print('\n')

    print('  Palette:')
    for i in range(16):
        slot = f'{i:02x}'
        hex6 = s.palette.get(slot, '')
        if hex6:
            print(f'  {_bg_block(hex6)} base{slot} #{hex6}')
    print()


_COLOR_SCHEME_RE = re.compile(r'config\.color_scheme\s*=[^\n]*')
_THEME_KEY_RE = re.compile(r'"theme"\s*:\s*"[^"]*"')


def set_wezterm(config_path, scheme_name: str) -> None:
    p = Path(config_path)
    data = p.read_text()
    if not _COLOR_SCHEME_RE.search(data):
        raise ValueError(f'no config.color_scheme line found in {config_path}')
    p.write_text(_COLOR_SCHEME_RE.sub(f'config.color_scheme = "{scheme_name} (base16)"', data))


def set_claude(settings_path, yaml_path) -> str:
    s = parse_scheme(yaml_path)
    if not s:
        raise ValueError(f'could not parse scheme: {yaml_path}')
    claude_theme = 'light-ansi' if s.variant == 'light' else 'dark-ansi'
    p = Path(settings_path)
    data = p.read_text()
    if not _THEME_KEY_RE.search(data):
        raise ValueError(f'no "theme" key found in {settings_path}')
    p.write_text(_THEME_KEY_RE.sub(f'"theme": "{claude_theme}"', data))
    return claude_theme


def ensure_schemes(schemes_dir: Path) -> Path:
    base16_dir = schemes_dir / 'base16'
    if (schemes_dir / '.git').exists():
        subprocess.run(['git', '-C', str(schemes_dir), 'pull', '--quiet', '--ff-only'],
                       capture_output=True)
    else:
        schemes_dir.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            'git', 'clone', '--depth=1', '--filter=blob:none', '--sparse',
            'https://github.com/tinted-theming/schemes', str(schemes_dir), '--quiet',
        ], check=True)
        subprocess.run(
            ['git', '-C', str(schemes_dir), 'sparse-checkout', 'set', 'base16'],
            check=True,
        )
    if not base16_dir.exists():
        raise FileNotFoundError(f'base16 schemes not found at {base16_dir}')
    return base16_dir
