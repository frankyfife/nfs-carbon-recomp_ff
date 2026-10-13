# Porting the NFS Most Wanted native Direct3D 12 renderer to Carbon

Goal: the native renderer of
[frankyfife/NFSMW-Recompiled_ff](https://github.com/frankyfife/NFSMW-Recompiled_ff) (`app/src/native/`,
GPL-3.0) in this project, on the EU Collector's Edition XEX (media ID 5E74E60D).

How it works in MW: hooks on the game's statically linked Xbox D3D library record every draw and
resolve of a frame (the device's register shadow, the microcode that runs, resolve arguments, vertex
data that the game may refill). At the swap the frame goes to a thread with its own D3D12 device that
draws it (`renderer.cpp`, game-independent: it works from Xenos registers and microcode). The SDK side
(already in this project's SDK through `patches/rexglue-nfsmw-ff-pc.patch`) shows that frame in the
game's window (`IssueSwap` -> `NfsmwNativeFrame`) and skips the emulated draws
(`NfsmwNativeSkipEmulation`).

The port therefore needs Carbon's addresses and device layout for the recording layer
(`parallel.cpp`); `renderer.cpp` comes over unchanged.

## Tools (`../tools/scripts`)

- `ppcfuncs.py`: guest functions and their instructions from a `generated/default` tree (both projects
  carry every PPC instruction as a comment).
- `match_d3d.py`: finds the D3D library in each game (block around the `Vd*` callers) and matches
  functions by instruction sequence with numbers blanked.
- `match_by_callers.py`: matches through the game code that calls the library (EA's engine is far more
  alike between the games than the library, a newer XDK in Carbon).
- `sidebyside.py`, `find_const.py`: side-by-side diff of two functions; functions using given
  immediates (PM4 headers, register numbers).

D3D library: MW `8258E5E0-825A9858`, Carbon `826DB208-82703A20`. 533 of 773 functions match at >= 90 %;
the draw, resolve, swap and shader functions do not (rewritten in Carbon's XDK).

## Functions

| Role | MW | Carbon | Notes |
|---|---|---|---|
| DrawIndexed (dev, prim, base, start, count) | `82593C50` | `826DDE68` | same arguments |
| DrawVertices (dev, prim, start, count) | `82593A10` | `826DDA78` | same arguments |
| BeginVertices (dev, prim, count, stride) -> data | `825932D8` | `826DCFA0` | same arguments and result |
| Resolve (dev, flags, rect*, tex*, point*, ..., slice) | `82592538` | `826F35E0` | same argument registers |
| Swap | `825989D8` | `826E27A8` | Carbon's only `VdSwap` caller |
| New command buffer segment -> write pointer | `82597268` | `826DA808` | |
| Shader loads (IM_LOAD) of a draw (dev) | `825A3AF0` | `826FBB68` | |
| Occlusion query ZPD event (dev, query, which) | `8258EA28` | `826ECC28` | same query layout |
| SetStreamSource (dev, stream, buffer, offset, stride) | `8258D968` | `826D7F40` | writes the fetch shadow itself |
| Flush (dirty state before a draw) | `825A40C0` | inlined into every draw | see dirty masks |

Other Carbon draw functions with the inlined flush: `826DD490` (one internal caller),
`826DE280`, `826DE700`, `826F6A88` (no direct callers: reached through pointers). Not identified yet.

## Device layout

| Field | MW | Carbon |
|---|---|---|
| Command buffer write pointer / end | +0 / +8 | +48 / +56 |
| Dirty mask, VS float constants (one bit per 16 registers) | +16 | +0 |
| Dirty mask, PS float constants | +24 | +8 |
| Register shadow 0x2000 (16) | 11456 | 10240 |
| 0x2100 (21) | 11532 | 10316 |
| 0x2180 (5) | 11616 | 10400 |
| 0x2200 (12) | 11636 | 10420 |
| 0x2280 (21) | 11684 | 10468 |
| 0x2300 (38) | 11768 | 10552 |
| 0x2380 (8) | 11920 | 10704 |
| 0x4000 VS constants (1024) | 1920 | 1792 |
| 0x4400 PS constants (1024) | 6016 | 5888 |
| 0x4800 fetch constants (192) | 1152 | 1024 |
| 0x4900 (40) | 10112 | 9984 |
| Fetch constant 95 (stream 0; stream s uses 95 - s) | 1912 | 1784 |
| Vertex shader object | 12948 | 12416 |
| Pixel shader object | 12944 | 12412 |
| Vertex declaration | 11408 | 11540 |
| Index buffer object | 12532 | 12156 |
| Stream s buffer object | 12556 + 8s + 4 | 12180 + 4s |
| Stream s stride / 4 (byte) | 12688 + s | 12248 + s |

Carbon writes the vertex fetch constant at SetStreamSource without the type bits (`& 3`); MW's recorder
checks them.

## Objects

| Object | MW | Carbon |
|---|---|---|
| Index buffer: address | +12 (16-bit indices) | +24; bit 31 of +0 set = 32-bit indices |
| Pixel shader: microcode | address at +12 | `ps[+24] + h[+40]`, size bytes `h[+44]`, `h = ps + ps[+64]` |
| Vertex shader: microcode | address at +40 | variants: entry `e = vs + vs[+896 + 8 i]`, address `vs[+32] + e[+872]`, size `e[+876]` |
| Texture (resolve destination): fetch constant | +16..+36 | +28..+48 |
| Occlusion query: tiles, report addresses | +144, +24 + 4 i | same |

Shader loads: Carbon writes `IM_LOAD` both plain (`0xC0012700`) and predicated (`0xC0012701`); MW's scan
compares the header exactly and must accept bit 0. Vertex shaders are patched ahead of time into variants
inside the shader object, so the loaded address (type 0) is what runs.

## State that bypasses the shadow (found while testing, 2026-10-13)

The first native frames showed the font atlas on every HUD sprite. Three differences to MW's library:

1. **Shader constants loaded from memory.** Before each shader load, `sub_826FB970` writes
   `LOAD_ALU_CONSTANT` packets (`0xC0022F00`: physical address, first dword, dword count) that copy the
   shader object's own float constants into the registers, past the device shadow. The scan of the
   shader load function picks them up and the recorder lays them over the draw's registers
   (`constant_loads_`); about 22,000 per 10 s on the title screen.
2. **`VGT_INDX_OFFSET` (0x2102) only in the command buffer.** DrawVertices writes its start vertex
   there (DrawIndexed and BeginVertices write 0); MW's DrawVertices also kept it in the shadow. All
   HUD sprites are 4-vertex `DrawVertices` from one large buffer, so without it every sprite drew the
   first one. The recorder sets the register per draw. **This was the texture bug.**
3. **Front buffer.** Taken from the swap's texture argument (`r4`, fetch constant at `+28`) instead of
   the last resolve of the frame.

Diagnostics in `parallel.cpp`: `NATIVE_DEBUG_FRAME=<n>` logs every draw and resolve of frame n;
`NATIVE_SAVE_FRONT=<png>` saves the shown frame every 300 frames; every 10 s the log has the shader
load scan counts.

Status: the title screen renders correctly through the native renderer (also with
`native_renderer_skip_emulation`, at 2x scale: 2560x1440). Menus, races and free roam not verified yet.

## Plan

1. Copy `renderer.{h,cpp}`, `guest.h`, `sdk_cvars_local.h` from MW; adapt `parallel.cpp` to the tables
   above; hooks as `REX_FUNC` overrides of the Carbon functions.
2. Build the SDK's Xenos shader translator into `nfscarbon.exe` as MW's `app/CMakeLists.txt` does.
3. Test with `--native_renderer=true --native_renderer_skip_emulation=false` first (both draw), then
   with skipping, and compare pictures.
