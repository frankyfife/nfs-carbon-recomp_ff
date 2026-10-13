# Handoff: work for a cloud session (2026-10-13)

Branch `native-d3d12-wip` (based on `pc-build`). The PC build is for the user's **EU Collector's Edition**:
title ID `454107EC`, XEX media ID `5E74E60D`. This is a different build from the original author's, so
addresses in public patches or in the upstream manifest may be shifted.

## What a cloud session can and cannot do

The cloud session does **not** have the game: no ISO, no `game/`, no `generated/default/`, no recompiled
code, and no Windows/D3D12/GPU. The game is copyrighted, so do not try to obtain it. You also cannot
build: `CMakeLists.txt` takes the SDK's shader translator from `../reference/rexglue-sdk`, which is a
local checkout (upstream ReXGlue SDK `50daf68` + `patches/rexglue-nfsmw-ff-pc.patch`).

So: research, reading and writing code, docs. Every change is built and tested later on the user's
Windows PC. Keep changes small and self-contained, explain in the commit message how to test them, and
do not touch `master`. Push to this branch (or a branch made from it).

## Task 1: 60 fps for Carbon (research + preparation)

Findings so far:
- Carbon runs at 30 fps, like on the console. The NFS Most Wanted trick (a faster guest vblank,
  `guest_vblank_rate`, as with Xenia Canary's `framerate_limit`) does **not** work here. Measured with
  a 60 fps target: the game thread still idles ~31 ms per frame. Menus and some scenes do run faster,
  so the cap is in the game's own frame timing (a fixed 1/30 s step or a wait for 2 vblanks per frame,
  for example), not in the emulator.
- The launcher (`launcher-windows/src/launcher_window.cpp`) offers 60 fps as experimental
  (`guest_vblank_rate=1000`).

To do:
1. Find public 60 fps patches for Need for Speed Carbon (Xbox 360). Start with
   `https://github.com/xenia-canary/game-patches` (`patches/454107EC - Need for Speed Carbon*.toml` or
   similar). Also check forums and mods for the PC version and the PS3/Wii U ports (frame timing, physics
   step, how a 60 fps mod for the PC version works). Write down for each patch: the hash/media ID it is
   for, the addresses, the original and patched values, and what the patched instructions mean. Try to
   say *what* the code does (e.g. "frame time constant 1/30", "vblank interval 2 for VdSwap"), so the
   address can be found again in this XEX.
2. If the patch is for another XEX build, describe how to find the same spot here. For example: a
   float constant `0x3D088889` (1/30), a `VdSetDisplayMode`/presentation interval, or a sequence of
   instructions to search for in `generated/default` (the generated C++ has each PPC instruction as a
   comment; see `tools/native-port/ppcfuncs.py` and `find_const.py`).
3. Prepare the code: a hook (override `sub_X` and call the original `__imp__sub_X`, declared with
   `extern "C" REX_FUNC(__imp__sub_X)`; see the end of `src/native/parallel.cpp`) or a patch to data at startup, behind a cvar, e.g.
   `carbon_60fps` (default off), with the addresses as placeholders if they can't be confirmed. Also list
   the risks: physics, animation, cutscene or audio timing tied to the frame rate.
4. Write the results into `docs/60fps.md`.

## Task 2: native D3D12 renderer (code without a test run)

Background: `docs/native-d3d12-port.md`. The renderer is ported from
`https://github.com/frankyfife/NFSMW-Recompiled_ff` (branch `windows-qt-launcher-and-fixes`,
`app/src/native/`). `src/native/parallel.cpp` is **generated**: `tools/native-port/port_parallel.py`
applies Carbon's changes to MW's `parallel.cpp`:

```
python port_parallel.py <MW app/src/native/parallel.cpp> src/native/parallel.cpp
```

Make changes in `port_parallel.py` (replacement pairs `r(old, new)`), not only in the output, and then
regenerate. The output must stay the same as the committed file except for your changes.

Status: the title screen renders correctly. The main menu and races render, but geometry and textures
are mostly wrong and the colours are wrong. Cause: Carbon's newer XDK D3D library writes state directly
into the command buffer instead of through the device's register shadow that MW's recorder reads.
Found so far (fixed): `LOAD_ALU_CONSTANT` shader constants, `VGT_INDX_OFFSET` (0x2102).

Latest findings from `NATIVE_STREAM_AUDIT=1` (walks the PM4 packets of each draw and compares them with
the shadow) and `NATIVE_STREAM_DUMP=<n>`: right before a draw the library writes
- type-0 writes of the **vertex fetch constants 0x48BA-0x48BF** (fetch 93-95 = streams 0-2), not equal to
  the shadow;
- type-0 at 0x5000 (3 values; not a real register: probably library data, ignore it), 0x2102;
- `SET_BIN_MASK_LO` (C0006000), a predicated `DRAW_INDX` (C0032201), C0015A01 (opcode 0x5A), C0004601.

Mismatches with the shadow at draw time: 0x47F0-0x47FF (PS constants c508-c511; probably library
scratch, check), 0x2305-0x2308, 0x2316/0x2317, 0x2324.

Raw dump of one draw:
```
80000000 000548BA 00000001 00000000 00000001 00000000 17A5FC83 100021E2 00025000 00000000 00025000
00000000 00002102 00000000 C0006000 FFFFFFFF C0032201 00000000 03480004 17A635F0 40000348 C0006000
80000000 C0015A01 0000001A 0938C6D9 C0004601 00000019
```

To do:
1. In the recorder, apply the register writes that the audit walk sees in the command buffer between the
   previous and the current draw on top of the shadow for that draw (the stream wins; keep the audit's
   register file). Only real registers: the shadow groups' ranges (see `kShadowGroups`) plus 0x2102;
   skip 0x5000-0x5FFF and others outside the groups. Behind an env var/cvar so it can be compared
   (`NATIVE_STREAM_STATE=1`, later the default if it helps).
2. Check `renderer.cpp` for the colour-format handling of render targets and resolves: Carbon probably
   uses formats MW didn't (e.g. 7e3 / 2_10_10_10 float, 16_16_16_16 float, `k_2_10_10_10_AS_16_16_16_16`,
   EDRAM HDR). Write down which formats are handled and add the missing ones (see the SDK's
   `src/graphics/` format tables in the ReXGlue SDK on GitHub for reference).
3. Update `docs/native-d3d12-port.md`.

## Testing (on the user's PC, not in the cloud)

`tools/native-port/run_menu.ps1` starts the game with the native renderer, sends key presses and saves
the native frame (`NATIVE_SAVE_FRONT`). Main menu: `-Keys "ESC@20","ESC@26"`. Before testing rename
`game/Movies` to `Movies.bak` (skips the intros), and rename it back afterwards.

## Results of the cloud session (2026-10-13)

Branch `claude/cloud-handoff-tasks-09ioid`, based on `native-d3d12-wip`. Nothing was built or run with the game.

**Task 1 (60 fps):**

- Written up in `docs/60fps.md`. No platform has a public 60 fps patch for Carbon: not Xenia (the repo's only
  Carbon file was removed in 2023), RPCS3, PCSX2 or Dolphin.
- The engine steps the simulation at a fixed 1/60 s (MW decomp, Carbon PC WidescreenFix), so 30 fps on the
  console means 2 steps per frame. Only the limiter has to go.
- Most likely it is `SetFPSLimiter(30)` / `LimitMinimumVideoTimeElapsed`, which is time-based and fits the
  measurement.
- Prepared:
  - `tools/find_60fps.py` lists the candidates in a `guest_image.bin`.
  - `src/frame_rate_hook.cpp` adds the cvars `carbon_60fps` (default off) and `carbon_60fps_patches`
    (verified data patches) and the CMake option `NFSCARBON_FPS_LIMITER_FUNC` (function hook).
  - The launcher passes `carbon_60fps` with its 60 fps setting.
- **Next:** dump the image, run the finder, enter the address.

**Task 2 (native renderer):**

1. **`NATIVE_STREAM_STATE=1|2|3`.** The recorder lays the register writes of the command buffer over the
   shadow. Done in `port_parallel.py`; `parallel.cpp` was regenerated and is otherwise unchanged. The audit
   now shares the walker, which fixes the reading of `SET_CONSTANT2` and adds the other packets.
2. **Formats in `renderer.cpp`:**
   - the fixed-16 render targets get the SDK's ÷32;
   - resolves keep the copy's format (float/HDR were clamped as R8G8B8A8) and its exponent bias; the
     write-back handles 4/8-byte formats; `NATIVE_RESOLVE_RGBA8=1` gives the old behaviour;
   - 14 more texture formats, among them DXN, DXT5A and the `_AS_16_16_16_16` variants;
   - still missing: 24_8, 10_11_11, 11_11_10 and CTX1.
3. **`docs/native-d3d12-port.md` updated.**

**Testing on the PC:**

1. The build: the renderer could not be compiled here (no D3D12/SDK headers); `parallel.cpp` and
   `frame_rate_hook.cpp` were checked against stub headers.
2. Main menu and a race with and without `NATIVE_STREAM_STATE=1` and `=3`, with `NATIVE_SAVE_FRONT`.
3. The `[native stream state]` lines and `unsupported texture: format N` in the log.
