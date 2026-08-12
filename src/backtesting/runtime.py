from __future__ import annotations

import os
from pathlib import Path
from xml.etree import ElementTree


def configure_font_environment(font_cache: Path) -> Path:
    cache = Path(font_cache).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    font_config = cache / 'fonts.conf'
    font_root = ElementTree.Element('fontconfig')
    font_directories = (
        [Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts']
        if os.name == 'nt'
        else [Path('/usr/share/fonts'), Path('/usr/local/share/fonts'), Path.home() / '.fonts']
    )
    for font_directory in font_directories:
        if font_directory.exists():
            ElementTree.SubElement(font_root, 'dir').text = font_directory.as_posix()
    ElementTree.SubElement(font_root, 'cachedir').text = cache.as_posix()
    ElementTree.ElementTree(font_root).write(
        font_config,
        encoding='utf-8',
        xml_declaration=True,
    )
    return font_config
