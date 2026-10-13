# 60 fps for NFS Carbon (research and preparation, 2026-10-13)

Build: EU Collector's Edition, title ID `454107EC`, XEX media ID `5E74E60D`.

**Status:** no public 60 fps patch for Carbon exists for any platform. The address of the frame limiter in
our XEX is not known yet. Prepared:

- the code that lifts the limiter once the address is known: `src/frame_rate_hook.cpp`, cvar `carbon_60fps`,
  default off;
- a tool that lists the candidates in a dumped image: `tools/find_60fps.py`.

## 1. Public patches

| Platform | Source | Frame rate patch for Carbon |
|---|---|---|
| Xbox 360 (Xenia) | [xenia-canary/game-patches](https://github.com/xenia-canary/game-patches), including its history | **none**: see below |
| PS3 (RPCS3) | patch.yml (mirror [RPCS3toArtemisPatches](https://github.com/DoSpamu/RPCS3toArtemisPatches)) | **none**; BLUS30016/BLES00020 have only colour correction, debug, unlock and SSL patches |
| PS2 (PCSX2) | [pcsx2_patches](https://github.com/PCSX2/pcsx2_patches) | **none**: widescreen, bloom and NTSC only |
| Wii (Dolphin) | GameSettings `RNSE69.ini` | **none**: an unlock code only |
| PC (v1.4) | [ThirteenAG WidescreenFixesPack](https://github.com/ThirteenAG/WidescreenFixesPack), `NFSCarbon.WidescreenFix/Misc.ixx` | `SimRate` (simulation rate = display rate; see 2.2) |

Notes on the 360 row:

- The only Carbon file the repo ever had was `454107EC - Need for Speed Carbon.patch.toml`. Gliniak added it
  in cd01ccf (2021) with a single patch, "Skip audio loop stuck code": `be32 0x826B4D38 = 0x38A00000`
  (`li r5,0`).
- It was deleted in f221a43 (2023, "Remove hashless patches") because it had no hash or media ID. Its build is
  unknown, so the address probably does not fit ours.
- The Most Wanted file (`454107D9`) has no frame rate patch either.

There is nothing to port. Sections 2 and 3 describe how the engine paces frames, so the right spot can be
found in our XEX.

## 2. How the engine paces frames

### 2.1 Most Wanted: decompilation and 360 recompilation (same "Speed" engine)

Sources:

- [dbalatoni13/nfsmw](https://github.com/dbalatoni13/nfsmw): `src/Speed/Indep/Src/Misc/Timer.cpp`,
  `Main.cpp`, `Main/Scheduler.h`, `Sim/Common/Simulation.cpp`; symbols for an Oct 2005 MW 360 prototype in
  `config/EUROPEGERMILESTONE/symbols.txt`.
- [SpeedBreaker](https://github.com/SpeedBreakerProject/speedbreaker): a static recompilation of MW 360 (US)
  that runs at 60 fps. See `runtime/game/frame_time.cpp` and `runtime/video/vblank_lock.h`.

Confirmed for MW:

- **The simulation runs a fixed 1/60 s step.** `Scheduler::Init(0.016666668f)` sets the step. The scheduler
  keeps the time left over, runs `floor(elapsed / step)` steps per frame and at most 4 to 6, and does not
  interpolate.
  - At 30 fps every frame runs **two** steps, so 60 fps needs no physics change: only the frame cap has to go.
  - WFP's source says so for Carbon too: "Consoles target 60 but run at 30".
- **The main loop.** It reads the time base (`mftb`) and calls `MainLoop(ms)` once `ms` exceeds
  `Tweak_MinimumRealTimeStep` (0.25). `MainLoop` then calls:
  - `PrepareRealTimestep(ms * 0.001)`, which caps the step at `MaxTicksPerTimestep` (4) × 1/60 and quantises
    it to 1/3600 s;
  - `Scheduler::Run`;
  - the game services;
  - `Main_DisplayFrame`;
  - `AdvanceRealTime`.
- **Frame limiter API.** `Timer.cpp` has `SetFPSLimiter(float fps)`, `ResetFPSLimiter()` and
  `GetMaxFPS()`.
  - They work on `LimitMinimumVideoTimeElapsed` and `DefaultLimitMinimumVideoTimeElapsed`, both 1/60 by
    default.
  - MW PC: `SetFPSLimiter__Ff` at 0x653FC0 writes 0x925990.
  - `RealTimeElapsed` starts at 2/30 (`0x3D888889`) and `RealTimeFramesElapsed` at 2.
- **`LOCK_TO_30` global.** `main` and `AIVehicleRacecar.cpp` declare it, and it sits next to
  `Scheduler::fgScheduler`. Its use is not decompiled yet.
- **MW 360 swap throttle.** The swap's interrupt callback argument is `0x0001000A` (presentation interval 1,
  threshold 10 %), so on MW the vblank is the frame clock.
  - SpeedBreaker reaches 60 fps by pacing the guest vblank.
  - That is the `guest_vblank_rate` approach, which **does not** work for Carbon (measured: the game thread
    still idles ~31 ms per frame).

### 2.2 Carbon PC: WidescreenFix "SimRate"

WFP sets `FrameTime = 1 / SimRate` and overwrites Carbon's 1/60 constants (x86 v1.4, for orientation only):

| WFP name | PC address | Default |
|---|---|---|
| PrepareRealTimestep NTSC frame time | 0x6B4CFB (data 0x9CBC14) | 1/60 |
| "MainLoop frametime (FPS lock)" | 0x6B79DF, `mov [esp+1C], 1/60` | 1/60 |
| FullSpeedMode frame time | 0x6B79F0 | 1/6 (10 × 1/60) |
| Unknown frame time 1, 2 (probably the Scheduler/Sim step) | 0x764A3F, 0x76AD07 | 1/60 |
| ESimTask frame time | 0x672EFB | 1/60 |
| Sim::QueueEvents frame time | 0x76AD57 | 1/60 |

- These are the **simulation step and the real-time quantum**, not a render cap. On PC the game runs at the
  display rate, and WFP keeps the sim in step with it.
- Carbon PC hooks: `MainLoop(float)`, `MiniMainLoop()` and `Sim::Internal::mLastFrameTime`.
- NFSCExtraOptions: `GameSpeed`, `WorldAnimationSpeed` and `HUDUpdateRate`; it has no fps option.

### 2.3 What caps Carbon 360 (inference, not confirmed)

- Measured: with a guest vblank every millisecond, the game thread still idles ~31 ms per frame, while menus
  and some scenes run faster.
- So the cap is **time-based in the game's own code**, not the D3D swap throttle.
- The likely mechanism is the limiter above: the game calls `SetFPSLimiter(30)` while racing and
  `ResetFPSLimiter()` in menus, and `MainLoop` (or the loop around it) sleeps until
  `LimitMinimumVideoTimeElapsed` has passed.
- Alternatives:
  - a `LOCK_TO_30`-style flag read by the scheduler or main loop;
  - a presentation interval of 2. This is unlikely, because the fast vblank would have helped.

## 3. Finding it in our XEX

Data globals in our build are at the same addresses as in the (non-public) NFS-CARBON-360-DECOMP, and code is
shifted by -0x150 (`docs/render-mode-addresses.md`). If that decomp names the timer globals, use its addresses
directly.

Otherwise:

1. Dump the image: run once with `REX_DUMP_GUEST_IMAGE=1`. 15 s after start, `guest_image.bin` is written next
   to the game.
2. Run `python tools/find_60fps.py --image guest_image.bin --init generated/default/nfscarbon_init.cpp
   --generated generated/default`. It lists:
   1. the timing constants and the code that loads them. Look for 1/30 `0x3D088889`, 1/60 `0x3C888889`,
      30.0 `0x41F00000`, 2/30 `0x3D888889`, 1/3600 `0x3991A2B4`, 65536.0 `0x47800000`, and the doubles 1/30
      `0x3FA1111111111111` and 1/60 `0x3F91111111111111`;
   2. **`SetFPSLimiter`-shaped functions**: a short function that divides by `f1` (`fdivs`) and stores the
      result to a global, with their call sites. **A call site that loads 30.0 into `f1` is the cap.** The
      global is `LimitMinimumVideoTimeElapsed`;
   3. the swap throttle argument: `0x0001000A` means interval 1, `0x0002000A` interval 2. Interval 2 would mean
      a presentation-interval cap after all;
   4. the functions that read the time base (`mftb`), i.e. the main loop and its timers;
   5. the callers of `KeDelayExecutionThread` and the wait imports. A time-based limiter sleeps there, and
      its caller chain leads to `MainLoop`.
3. Read the candidates in `generated/default` (every PPC instruction is a comment there;
   `tools/native-port/ppcfuncs.py` and `find_const.py` help).
4. **Quicker in a running game:** log the guest LR and the timeout of each `KeDelayExecutionThread` call on
   the main thread while racing. About 33 ms minus the frame's work points straight at the limiter.

## 4. Prepared code: `carbon_60fps` (default off)

Guest code cannot be patched like in Xenia: in the recompilation it is compiled C++, so a changed instruction
word does nothing. Two ways in instead:

- **Data:** `carbon_60fps_patches` = `ADDRESS:FROM:TO,...`. The address is hex, inside the XEX image
  (0x82000000-0x830D0000). Values are floats when they contain a `.` (a float FROM matches to 1e-4 relative),
  otherwise hex words.
  - A background thread checks every word each millisecond and writes TO only while the word holds FROM. A
    wrong address that holds something else therefore stays untouched, and the game setting the limit again
    is undone within a millisecond.
  - Example, once the limiter global is known: `--carbon_60fps=true
    --carbon_60fps_patches=82XXXXXX:0.033333:3C888889`. Give TO in hex: `0.016667` is not exactly 1/60
    (`3C88893B`).
  - Also usable for a `LOCK_TO_30`-style flag: `82XXXXXX:1:0`.
  - Logs: `[60fps] ...: ... -> ... (first time)`, then the write count every 30 s.
- **Function:** configure with `-DNFSCARBON_FPS_LIMITER_FUNC=82XXXXXX` (the `SetFPSLimiter`-shaped function
  from step 2.2, 8 hex digits). This hooks it: with `carbon_60fps`, an fps below 60 becomes 60 before the
  original runs (log: `[60fps] frame limiter 30.0 fps -> 60 fps`).

The launcher passes `carbon_60fps=true` with its "60 · Experimental" setting, which already gives the guest a
vblank every millisecond (`guest_vblank_rate=1000`). Without an address the cvar only logs that it has
nothing to do.

## 5. Risks at 60 fps

- **Physics, AI and game speed:** the step stays 1/60, so only the number of steps per frame changes (1
  instead of 2).
  - Risk: frames with 0 or 2 steps (no interpolation) show as hitches. SpeedBreaker had to snap the frame
    time to whole vblanks for MW.
  - The `frame_pacing_fps` clock should keep that rare; check on the F4 overlay.
- **Effects spawned per frame:** NOS light trails come out half as long (drawn from the last frames). Sparks
  and contrails double in density. WFP has `FixNOSTrailLength`, `ContrailTargetFPS` and `SparkTargetFPS` for
  this on PC.
- **In-game cutscenes and scripted camera paths:** the NFS UG/UG2 60 fps patches report double-speed scenes.
  Watch race intros and the canyon duel intro.
- **FMVs:** timer-driven (the XMV player waits for its own 29.97 fps), so not affected.
- **Audio:** no reports. Engine and tyre sounds follow the sim, not the frame.
- **HUD and UI:** rates tied to frames: map cursor, menu animations, drift score counters (WFP warns about
  drift scoring's 60.0 values).
- **Replays and the Joylog** record time steps. Replays may depend on them; unverified.
- **GPU load:** twice the frames. On Android the native renderer and tiling cost already limit 30 fps, so
  this is a PC-only setting for now.

## 6. Testing (on the PC)

1. Dump the image, run the finder, pick the address (section 3).
2. Run with `--carbon_60fps=true --carbon_60fps_patches=...` (or the CMake option) and the launcher at 60.
3. Check:
   - the `[60fps]` log lines;
   - the F4 overlay frame time (16.7 ms while racing);
   - car handling and lap times against 30 fps (same speed?);
   - race intros, NOS trails, menus.
4. If menus run at double speed, limit the patch to the race (FROM only matches the race's 1/30).
