#!/usr/bin/python3
"""Build a self-contained, square SVG wrapper without modifying GRUB's PNG."""
import base64
from pathlib import Path
root=Path(__file__).resolve().parent.parent
png=(root/'assets/vendor/grub-logo.png').read_bytes()
encoded=base64.b64encode(png).decode('ascii')
svg=f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="256" height="256" viewBox="0 0 256 256">
  <title>GNU GRUB</title>
  <desc>GNU GRUB logo by Karol Krenski, public domain. Original pixels preserved. See assets/NOTICE.md.</desc>
  <image x="6" y="38" width="244" height="180" preserveAspectRatio="xMidYMid meet" xlink:href="data:image/png;base64,{encoded}"/>
</svg>
'''
(root/'assets/icons/rust-boot-manager.svg').write_text(svg)
