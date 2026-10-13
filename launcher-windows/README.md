# Windows launcher (Qt 6)

A launcher for `nfscarbon.exe`: game data (an ISO, extracted once into `game_root_cache\`, or an
extracted folder), renderer, display, frame rate and image quality. It saves its settings to
`launcher.ini` and starts the game with the matching `--name=value` arguments (`Command line…`
shows them).

## Origin and license

Adapted from the Qt launcher of
[frankyfife/NFSMW-Recompiled_ff](https://github.com/frankyfife/NFSMW-Recompiled_ff)
(`launcher-windows/`), itself a modified version of
[madelrandel-blip/NFSMW-Recompiled](https://github.com/madelrandel-blip/NFSMW-Recompiled).
Like its source, the code in this folder is licensed under the **GNU GPL v3.0** (see `LICENSE`).
Changed for NFS Carbon on 2026-10-13: Carbon branding and icon colors, `nfscarbon.exe` lookup,
renderer choice (Xenos / native Vulkan), Most Wanted-only options removed (Black Edition,
unlock all, field of view, car LOD, post-processing, MSAA and mipmaps of the MW native renderer),
30 fps as the default target.

## Building

```powershell
powershell -ExecutionPolicy Bypass -File launcher-windows\build.ps1
```

Needs Qt 6 for MSVC 2022 x64 (`-QtDir`, `QT_DIR`, or `D:\Qt\6.*\msvc2022_64`) and the Visual
Studio 2022 C++ build tools. The result is `launcher-windows\out\NFS_Carbon.exe` with its Qt DLLs;
from there it finds the game in `out\build\win-amd64-vk\`.
