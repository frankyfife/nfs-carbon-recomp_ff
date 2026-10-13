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

## Registers from the command buffer: `NATIVE_STREAM_STATE` (2026-10-13, not tested yet)

`NATIVE_STREAM_AUDIT=1` showed that Carbon's library also writes state the shadow never sees. It writes
type-0 packets for the **vertex fetch constants of streams 0-2 (0x48BA-0x48BF)**: with the type bits, which
the shadow lacks (`17A5FC83` against `17A5FC80`), and for streams 1-2 not equal to the shadow.

It also writes type-0 packets to 0x5000-0x5002. These are `SHADER_CONSTANT_FLUSH_FETCH_0-2` in the SDK's
register table: a mask of the fetch constants that changed, not state, and ignored here.

Further mismatches at draw time: 0x47F0-0x47FF, 0x2305-0x2308 (`PA_CL_GB_HORZ_*_ADJ`, `SQ_VS_CONST`,
`SQ_PS_CONST`), 0x2316/0x2317 (`VGT_VERTEX_REUSE_BLOCK_CNTL`, `VGT_OUT_DEALLOC_CNTL`) and 0x2324
(`RB_SAMPLE_COUNT_CTL`).

**How the recorder takes them.** With `NATIVE_STREAM_STATE=<mask>` (1 draws, 2 resolves, 3 both):

1. **Walks.** The hooks walk what the library wrote between two hooked calls (`RecordCall`; a segment
   change ends a walk with the rest of the old segment). They collect the register writes as the SDK's
   command processor makes them: type 0 and 1, `SET_CONSTANT`, `SET_CONSTANT2`/`SET_SHADER_CONSTANTS`
   (register index), `LOAD_ALU_CONSTANT` (values from memory), and `REG_RMW`.
2. **At each recorded item:**
   - the writes before its last draw packet are laid over the shadow;
   - the writes after it (state the library sets after the draw) wait for the next item.
3. **How long a value holds.** A register keeps the command buffer's value until the command buffer
   writes it again, or the shadow changes (a Set call the command buffer has not shown yet). Then the
   shadow's value comes back.
4. **Lost walks.** If a walk is lost (the write pointer moved to another segment unseen), every register
   goes back to the shadow's value.

Only registers of the shadow groups are taken. `NATIVE_STREAM_STATE_REGISTERS=48BA-48BF,2102` narrows the
set (hex, ranges), for finding out which registers matter. The DrawVertices vertex copies read the stream
fetch constants as recorded (so with the command buffer's values).

Every 10 s the log has a line `[native stream state]` with:

- the items that got registers from the command buffer;
- the registers most often taken, with the command buffer's and the shadow's value;
- writes outside the shadow, unknown `REG_RMW`s, indirect buffers (not followed), and lost walks.

**Audit fix.** The audit now uses the same walker. Before, it read `SET_CONSTANT2` (0x55) like
`SET_CONSTANT`, as type and index; it takes an absolute register index. It also did not count
`SET_SHADER_CONSTANTS`, `LOAD_ALU_CONSTANT` or `REG_RMW`.

**Checked here** (Linux, against stub headers, since the cloud has no Windows or SDK build):

- a synthetic command buffer through the real hooks, with ASan/UBSan: stream values over the shadow, writes
  after the draw packet for the next item, shadow changes, `SET_CONSTANT2`, `SET_CONSTANT` type 1,
  `LOAD_ALU_CONSTANT`, resolves, lost walks;
- the recorded change list replays to the recorder's register file;
- without the variable, nothing changes.

**To test on the PC:**

1. `NATIVE_STREAM_STATE=1`, then 3, against without, in the main menu and a race, with `run_menu.ps1` and
   `NATIVE_SAVE_FRONT`.
2. Read the `[native stream state]` lines.
3. If a register makes things worse, narrow the set with `NATIVE_STREAM_STATE_REGISTERS`.

## Formats (2026-10-13)

**Render targets** (`ColorFormat`):

| Guest format | Host format |
|---|---|
| 8_8_8_8 (and GAMMA) | R8G8B8A8 |
| 2_10_10_10 (and AS_10_10_10_10) | R10G10B10A2 |
| 16_16, 16_16_16_16 | SNORM |
| 16_16_FLOAT | R16G16_FLOAT |
| 32_FLOAT | R32_FLOAT |
| 32_32_FLOAT | R32G32_FLOAT |
| everything else: 2_10_10_10_FLOAT (7e3), 2_10_10_10_FLOAT_AS_16_16_16_16, 16_16_16_16_FLOAT | R16G16B16A16_FLOAT, as in the SDK without ROV |

- **New:** the SDK divides the output for 16_16 and 16_16_16_16 by 32 (`color_exp_bias - 5`), because they
  are -32...32 on the guest and -1...1 as SNORM. MW's renderer did not, so values above 1/32 were clipped.
  Resolves of such a target multiply by 32 again.

**Resolves.** Every copy was R8G8B8A8 (depth: R32_FLOAT), whatever the game copied, so float/HDR targets
lost everything outside 0-1. Now:

- **Destination format.** The destination has the copy's format (`RB_COPY_DEST_INFO.copy_dest_format`):
  8, 8_8, 2_10_10_10, 16, 16_16, 16_16_16_16 (UNORM), 16 to 16_16_16_16 FLOAT, 32 to 32_32_32_32 FLOAT.
  Formats without a host render target format stay R8G8B8A8.
- **Exponent bias.** The copy's exponent bias (`copy_dest_exp_bias`) is applied (it was ignored).
- **Pipelines.** Resolve pipelines are made per destination format.
- **Write-back.** `WriteBackSmallResolves` (the copies the CPU reads, such as the exposure) also writes back
  4- and 8-byte formats. They are written as the first texel of each block at a scale; R8G8B8A8 is still
  averaged.
- **Old behaviour.** `NATIVE_RESOLVE_RGBA8=1` restores it, for comparing.

**Textures** (`TextureFormat`):

- Before, only these 16 were handled: DXT1/2_3/4_5, 8, 8_8, 5_6_5, 1_5_5_5, 4_4_4_4, 8_8_8_8, 2_10_10_10,
  16_16, 16_16_16_16, 16_FLOAT, 16_16_FLOAT, 16_16_16_16_FLOAT and 32_FLOAT.
- **New**, formats the SDK's D3D12 texture cache also copies unchanged:
  - 8_A;
  - 8_8_8_8_AS_16_16_16_16, DXT1/DXT2_3/DXT4_5_AS_16_16_16_16 and 2_10_10_10_AS_16_16_16_16 (only the
    filtering precision differs);
  - DXN (BC5, normal maps) and DXT5A (BC4);
  - 16 (UNORM);
  - 16_EXPAND, 16_16_EXPAND and 16_16_16_16_EXPAND (FLOAT);
  - 32_32_FLOAT and 32_32_32_32_FLOAT.
- **Still missing**, because they need a conversion (the SDK's load shaders):
  - 24_8 and 24_8_FLOAT (depth sampled as a texture: shadow maps, unless they come from a resolve);
  - 10_11_11 and 11_11_10 (with their AS_16_16_16_16 variants);
  - CTX1, DXT3A, 6_5_5, Y1_Cr_Y0_Cb_REP and Cr_Y1_Cb_Y0_REP.

  Each one prints `unsupported texture: format N` (N is `xenos::TextureFormat`). The 10 s log counts them.
  The next step is to collect the numbers Carbon prints.

`renderer.cpp` was identical to MW's until these changes; they are the first Carbon-side changes in it.

## Plan

1. Copy `renderer.{h,cpp}`, `guest.h`, `sdk_cvars_local.h` from MW; adapt `parallel.cpp` to the tables
   above; hooks as `REX_FUNC` overrides of the Carbon functions.
2. Build the SDK's Xenos shader translator into `nfscarbon.exe` as MW's `app/CMakeLists.txt` does.
3. Test with `--native_renderer=true --native_renderer_skip_emulation=false` first (both draw), then
   with skipping, and compare pictures.
