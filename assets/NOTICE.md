# Icon sources

## GNU GRUB

- Original artwork: Karol Kreński.
- Project page linking the original logo: https://www.gnu.org/software/grub/
- Original gallery: http://www.inf.sgsp.edu.pl/pub/MALUNKI/LOGO/
- Source record and permission: https://commons.wikimedia.org/wiki/File:Grub_logo_large.png
- Downloaded image: https://upload.wikimedia.org/wikipedia/commons/8/81/Grub_logo_large.png
- Permission stated by the source: released into the public domain by its creator.
- Original SHA-256: `ffcf36f06bfacf1b8b925e61c444043be679fbeb0404641eebfca7a06335a4b8`.

`vendor/grub-logo.png` is the unchanged original image. `icons/rust-boot-manager.svg`
embeds those same PNG bytes in a transparent square SVG for desktop icon sizing.
Rebuild the wrapper with `python3 scripts/build-icons.py`; it performs no raster editing.

## Windows 11

`icons/rust-boot-manager-windows11.svg` defines the blue four-pane mark using basic
vector geometry. Windows is a Microsoft trademark; the icon identifies the target
operating system for the Windows boot shortcut.

The MIT license in the repository applies to this project's code, not ownership
of third-party trademarks. Both assets are bundled locally and require no runtime
network access.
