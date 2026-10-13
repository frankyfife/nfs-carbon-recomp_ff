"""Turns NFSMW-Recompiled_ff app/src/native/parallel.cpp into Carbon's.

Every change is an exact replacement of MW text (it fails if MW's file
differs), so the diff to MW stays readable. Addresses and offsets: see
docs/native-d3d12-port.md.

    python port_parallel.py <mw parallel.cpp> <out parallel.cpp>
"""
import sys

src = open(sys.argv[1], encoding="utf-8", newline="").read()
crlf = "\r\n" in src
t = src.replace("\r\n", "\n")
R = []


def r(old, new):
    R.append((old, new))


r('''// Native renderer in the running game, next to the emulated GPU (stage 4 of
// docs/NATIVE_RENDERER.md; the Qt launcher's default since 2026-10-01).
//
// With --native_renderer=true the D3D hooks (render_census.cpp ->
// render_capture.cpp) record every draw and resolve of a frame: the device's
// register shadow, the microcode that runs and the resolve arguments. At the''',
  '''// Native renderer in the running game, next to the emulated GPU. Ported from
// NFSMW-Recompiled_ff (app/src/native/parallel.cpp, GPL-3.0) to NFS Carbon's
// D3D library: addresses, device layout and objects in
// docs/native-d3d12-port.md, made with tools/scripts/port_parallel.py.
//
// With --native_renderer=true the D3D hooks at the end of this file record
// every draw and resolve of a frame: the device's register shadow, the
// microcode that runs and the resolve arguments. At the''')

r('''constexpr ShadowGroup kShadowGroups[] = {
    {0x2000, 16, 11456},  {0x2100, 21, 11532},   {0x2180, 5, 11616},
    {0x2200, 12, 11636},  {0x2280, 21, 11684},   {0x2300, 38, 11768},
    {0x2380, 8, 11920},   {0x4000, 1024, 1920},  {0x4400, 1024, 6016},
    {0x4800, 192, 1152},  {0x4900, 40, 10112},
};''',
  '''// Carbon's D3D library keeps the same groups as MW's, at other offsets (from
// the inlined flush of its draw functions, e.g. sub_826DDE68).
constexpr ShadowGroup kShadowGroups[] = {
    {0x2000, 16, 10240},  {0x2100, 21, 10316},   {0x2180, 5, 10400},
    {0x2200, 12, 10420},  {0x2280, 21, 10468},   {0x2300, 38, 10552},
    {0x2380, 8, 10704},   {0x4000, 1024, 1792},  {0x4400, 1024, 5888},
    {0x4800, 192, 1024},  {0x4900, 40, 9984},
};''')

r('''constexpr uint32_t kDeviceVertexShader = 12948, kDevicePixelShader = 12944,
                   kDeviceIndexBuffer = 12532;
// Vertex streams (SetStreamSource sub_8258D968: offset and buffer at +12556
// + 8 s, stride / 4 as a byte at +12688 + s), the vertex declaration (its
// stream count - 1 at +12) and the shadow of fetch constant 95 (stream 0;
// the flush sub_825A2D80 writes stream s to fetch constant 95 - s).
constexpr uint32_t kDeviceStreams = 12556, kDeviceStreamStrides = 12688,
                   kDeviceVertexDeclaration = 11408, kDeviceFetch95 = 1912;''',
  '''constexpr uint32_t kDeviceVertexShader = 12416, kDevicePixelShader = 12412,
                   kDeviceIndexBuffer = 12156;
// Vertex streams (SetStreamSource sub_826D7F40: buffer object at +12180 +
// 4 s, stride / 4 as a byte at +12248 + s) and the shadow of fetch constant
// 95 (stream 0; stream s is fetch constant 95 - s, which SetStreamSource
// writes itself).
constexpr uint32_t kDeviceStreamBuffers = 12180, kDeviceStreamStrides = 12248,
                   kDeviceFetch95 = 1784;
// Command buffer write pointer, and the dirty masks of the vertex and pixel
// shader float constants (one bit per 16 registers, the highest first).
constexpr uint32_t kDeviceWritePointer = 48, kDeviceDirtyVsConstants = 0,
                   kDeviceDirtyPsConstants = 8;''')

r('''// Entry indices (tools/renderprobe/d3d_layer.json).
enum : int {
  kEntryFlush = 82,  // sub_825A40C0: writes the dirty state out before a draw
  kEntrySegment = 35,  // sub_82597268: a new command buffer segment (returns its write pointer)
  kEntryResolve = 10,
  kEntryBeginVertices = 11,
  kEntryDrawVerticesUP = 12,
  kEntryDrawVertices = 13,
  kEntryDrawIndexed = 14,
};''',
  '''// Hooked entry points (MW's numbering, kept for the recorder).
enum : int {
  kEntrySegment = 35,  // sub_826DA808: a new command buffer segment (returns its write pointer)
  kEntryResolve = 10,  // sub_826F35E0
  kEntryBeginVertices = 11,  // sub_826DCFA0
  kEntryDrawVertices = 13,  // sub_826DDA78
  kEntryDrawIndexed = 14,  // sub_826DDE68
};''')

r('''  uint32_t index_address = 0;
  bool up = false;''', '''  uint32_t index_address = 0;
  bool index_32bit = false;
  bool up = false;''')

r('''void Parallel::Before(int entry, const uint32_t* args, uint8_t* base) {
  if (entry != kEntryFlush) {
    return;
  }
  const uint8_t* device = base + args[0];
  const uint64_t vs = (uint64_t(LoadBE32(device + 16)) << 32) | LoadBE32(device + 20);
  const uint64_t ps = (uint64_t(LoadBE32(device + 24)) << 32) | LoadBE32(device + 28);''',
  '''// Before a draw: Carbon's draws flush the dirty state themselves (MW called a
// flush function), and clear the masks while doing it.
void Parallel::Before(int entry, const uint32_t* args, uint8_t* base) {
  if (entry != kEntryDrawIndexed && entry != kEntryDrawVertices &&
      entry != kEntryBeginVertices) {
    return;
  }
  const uint8_t* device = base + args[0];
  const uint64_t vs = (uint64_t(LoadBE32(device + kDeviceDirtyVsConstants)) << 32) |
                      LoadBE32(device + kDeviceDirtyVsConstants + 4);
  const uint64_t ps = (uint64_t(LoadBE32(device + kDeviceDirtyPsConstants)) << 32) |
                      LoadBE32(device + kDeviceDirtyPsConstants + 4);''')

r('''      // (dev, prim, base, start, count); 16-bit indices at index buffer +12.
      const uint32_t index_buffer = LoadBE32(device + kDeviceIndexBuffer);
      if (!index_buffer) {
        return;
      }
      item.indexed = true;
      item.count = args[4];
      item.index_address = GuestToPhysical(LoadBE32(base + index_buffer + 12)) + 2 * args[3];''',
  '''      // (dev, prim, base, start, count); the index buffer's address at +24,
      // 32-bit indices when bit 31 of +0 is set (16-bit otherwise).
      const uint32_t index_buffer = LoadBE32(device + kDeviceIndexBuffer);
      if (!index_buffer) {
        return;
      }
      item.indexed = true;
      item.index_32bit = (LoadBE32(base + index_buffer) & 0x80000000u) != 0;
      item.count = args[4];
      item.index_address = GuestToPhysical(LoadBE32(base + index_buffer + 24)) +
                           (item.index_32bit ? 4 : 2) * args[3];''')

r('''    } else if (LoadBE32(device + kDeviceStreams + 4)) {
      item.stream0_stride_words = device[kDeviceStreamStrides];
    }''',
  '''    } else if (LoadBE32(device + kDeviceStreamBuffers)) {
      item.stream0_stride_words = device[kDeviceStreamStrides];
    }''')

r('''      // (dev, prim, start, count): every stream of the vertex declaration,
      // stream s through fetch constant 95 - s (its shadow at device +1912 -
      // 8 s, written by the flush of this draw), stride at device +12688 + s.
      const uint32_t declaration = LoadBE32(device + kDeviceVertexDeclaration);
      const uint32_t streams =
          declaration ? std::min<uint32_t>(LoadBE32(base + declaration + 12) + 1, 16) : 0;
      const uint64_t start = args[2], count = args[3];
      for (uint32_t s = 0; s < streams; ++s) {
        if (!LoadBE32(device + kDeviceStreams + 8 * s + 4)) {
          continue;
        }
        const uint32_t d0 = LoadBE32(device + kDeviceFetch95 - 8 * s);
        const uint32_t d1 = LoadBE32(device + kDeviceFetch95 - 8 * s + 4);
        const uint64_t stride = uint64_t(device[kDeviceStreamStrides + s]) * 4;
        if ((d0 & 3) != 3 || !stride) {
          continue;
        }''',
  '''      // (dev, prim, start, count): every bound stream, stream s through fetch
      // constant 95 - s (as recorded for the draw: the shadow's at device
      // +1784 - 8 s, with NATIVE_STREAM_STATE the command buffer's), stride
      // at device +12248 + s. (The vertex declaration's stream count is not
      // read: a stream left bound from an earlier draw only costs a copy.)
      const uint64_t start = args[2], count = args[3];
      for (uint32_t s = 0; s < 16; ++s) {
        if (!LoadBE32(device + kDeviceStreamBuffers + 4 * s)) {
          continue;
        }
        const uint32_t d0 = _byteswap_ulong(last_shadow_[kFetch95Flat - 2 * s]);
        const uint32_t d1 = _byteswap_ulong(last_shadow_[kFetch95Flat - 2 * s + 1]);
        const uint64_t stride = uint64_t(device[kDeviceStreamStrides + s]) * 4;
        if (!(d0 & 0x1FFFFFFC) || !stride) {
          continue;
        }''')

r('''    } else {
      const uint32_t vs_address =
          vs_object ? GuestToPhysical(LoadBE32(base + vs_object + 40)) : 0;
      if (!vs_address) {
        return;
      }
      item.vs_code = AddCode(physical, vs_address, item.vs_dwords, false);
    }
    if (ps_object) {
      item.ps_code = AddCode(physical, GuestToPhysical(LoadBE32(base + ps_object + 12)),
                             item.ps_dwords, false);
    }''',
  '''    } else {
      // No load seen for this object: its first variant (entry at vs +
      // vs[+896], microcode at vs[+32] + entry[+872]).
      uint32_t vs_address = 0;
      if (vs_object) {
        const uint32_t entry = vs_object + LoadBE32(base + vs_object + 896);
        vs_address = GuestToPhysical(LoadBE32(base + vs_object + 32) + LoadBE32(base + entry + 872));
      }
      if (!vs_address) {
        return;
      }
      item.vs_code = AddCode(physical, vs_address, item.vs_dwords, false);
    }
    if (ps_object) {
      // Microcode at ps[+24] + h[+40], h = ps + ps[+64].
      const uint32_t header = ps_object + LoadBE32(base + ps_object + 64);
      item.ps_code = AddCode(
          physical,
          GuestToPhysical(LoadBE32(base + ps_object + 24) + LoadBE32(base + header + 40)),
          item.ps_dwords, false);
    }''')

r('''    for (int i = 0; i < 6; ++i) {
      item.dest_fetch[i] = LoadBE32(base + args[3] + 16 + 4 * i);
    }''',
  '''    // The destination texture's fetch constant (Carbon: at +28, MW +16).
    for (int i = 0; i < 6; ++i) {
      item.dest_fetch[i] = LoadBE32(base + args[3] + 28 + 4 * i);
    }''')

r('''    if (header == kIndirectLoad) {''',
  '''    // Carbon also writes IM_LOAD predicated (bit 0 of the header).
    if ((header & ~1u) == kIndirectLoad) {''')

r('''  wc.lpszClassName = L"NfsmwNativeRenderer";''', '''  wc.lpszClassName = L"NfsCarbonNativeRenderer";''')
r('''L"NFSMW - native renderer (parallel)",''', '''L"NFS Carbon - native renderer (parallel)",''')

r('''    d.indexed = item.indexed;
    d.index_address = item.index_address;''', '''    d.indexed = item.indexed;
    d.index_address = item.index_address;
    d.index_32bit = item.index_32bit;''')

# Hooks: MW's shader load and occlusion hooks become Carbon's, plus the draws,
# resolve, segment and swap that MW hooked in render_census.cpp.
r('''// The function of the D3D library that writes the shader loads (IM_LOAD) of a
// draw (device +0 is the command buffer write pointer, at the last dword
// written). The vertex shader address it loads is what runs: the library
// patches some vertex shaders into scratch memory.
extern "C" REX_FUNC(__imp__sub_825A3AF0);
extern "C" REX_FUNC(sub_825A3AF0) {
  if (!REXCVAR_GET(native_renderer)) {
    __imp__sub_825A3AF0(ctx, base);
    return;
  }
  // NFSMW_DUMP_IMAGE=<file>: the loaded game image (0x82000000, 13 MB) once,
  // for reverse engineering.
  // NFSMW_DUMP_IMAGE_EVERY=<seconds>: <file>.<n> every so often (to find
  // variables by how they change).
  // (Read once: getenv on every call -thousands per frame- was 30 % of the
  // game thread, in strchr.)
  static bool image_dumped = false;
  static auto last_dump = std::chrono::steady_clock::now();
  static int dump_index = 0;
  static const char* const dump_path = std::getenv("NFSMW_DUMP_IMAGE");
  static const char* const dump_every = std::getenv("NFSMW_DUMP_IMAGE_EVERY");
  if (const char* path = dump_path) {
    const char* every = dump_every;
    const auto now = std::chrono::steady_clock::now();
    if (!image_dumped ||
        (every && now - last_dump > std::chrono::milliseconds(int(std::atof(every) * 1000)))) {
      image_dumped = true;
      last_dump = now;
      const std::string name =
          every ? std::string(path) + "." + std::to_string(dump_index++) : std::string(path);
      if (FILE* out = std::fopen(name.c_str(), "wb")) {
        std::fwrite(base + 0x82000000u, 1, 13434880, out);
        std::fclose(out);
      }
    }
  }
  const uint32_t device = ctx.r3.u32;
  uint32_t before = LoadBE32(base + device);
  t_segment_start = 0;
  __imp__sub_825A3AF0(ctx, base);
  // When the library ran out of room it continued in a new segment: what it
  // wrote is from there on, the memory after `before` is older commands.
  if (t_segment_start) {
    before = t_segment_start;
  }
  Parallel::Get().ShaderLoadsWritten(base, device, before, LoadBE32(base + device));
}''',
  '''// The function of the D3D library that writes the shader loads (IM_LOAD) of a
// draw (device +48 is the command buffer write pointer, at the last dword
// written). The vertex shader address it loads is what runs: the library
// keeps patched variants of vertex shaders in the shader object.
extern "C" REX_FUNC(__imp__sub_826FBB68);
extern "C" REX_FUNC(sub_826FBB68) {
  if (!REXCVAR_GET(native_renderer)) {
    __imp__sub_826FBB68(ctx, base);
    return;
  }
  const uint32_t device = ctx.r3.u32;
  uint32_t before = LoadBE32(base + device + kDeviceWritePointer);
  t_segment_start = 0;
  __imp__sub_826FBB68(ctx, base);
  // When the library ran out of room it continued in a new segment: what it
  // wrote is from there on, the memory after `before` is older commands.
  if (t_segment_start) {
    before = t_segment_start;
  }
  Parallel::Get().ShaderLoadsWritten(base, device, before,
                                     LoadBE32(base + device + kDeviceWritePointer));
}

namespace {

// Calls a hooked entry point and records it (MW: render_census.cpp).
template <void (*Original)(PPCContext&, uint8_t*)>
void RecordCall(int entry, PPCContext& ctx, uint8_t* base) {
  if (!REXCVAR_GET(native_renderer)) {
    Original(ctx, base);
    return;
  }
  const uint32_t args[8] = {ctx.r3.u32, ctx.r4.u32, ctx.r5.u32, ctx.r6.u32,
                            ctx.r7.u32, ctx.r8.u32, ctx.r9.u32, ctx.r10.u32};
  Parallel::Get().Before(entry, args, base);
  Original(ctx, base);
  Parallel::Get().Record(entry, args, ctx.r3.u32, base);
}

}  // namespace

extern "C" REX_FUNC(__imp__sub_826DDE68);
extern "C" REX_FUNC(__imp__sub_826DDA78);
extern "C" REX_FUNC(__imp__sub_826DCFA0);
extern "C" REX_FUNC(__imp__sub_826F35E0);
extern "C" REX_FUNC(__imp__sub_826DA808);
extern "C" REX_FUNC(__imp__sub_826E27A8);

// DrawIndexed (dev, prim, base, start, count).
extern "C" REX_FUNC(sub_826DDE68) {
  RecordCall<__imp__sub_826DDE68>(kEntryDrawIndexed, ctx, base);
}
// DrawVertices (dev, prim, start, count).
extern "C" REX_FUNC(sub_826DDA78) {
  RecordCall<__imp__sub_826DDA78>(kEntryDrawVertices, ctx, base);
}
// BeginVertices (dev, prim, count, stride) -> vertex data the game fills.
extern "C" REX_FUNC(sub_826DCFA0) {
  RecordCall<__imp__sub_826DCFA0>(kEntryBeginVertices, ctx, base);
}
// Resolve (dev, flags, rect*, texture*, point*, ..., slice).
extern "C" REX_FUNC(sub_826F35E0) {
  RecordCall<__imp__sub_826F35E0>(kEntryResolve, ctx, base);
}
// A new command buffer segment -> its write pointer.
extern "C" REX_FUNC(sub_826DA808) {
  RecordCall<__imp__sub_826DA808>(kEntrySegment, ctx, base);
}
// Swap: the frame is complete.
extern "C" REX_FUNC(sub_826E27A8) {
  __imp__sub_826E27A8(ctx, base);
  if (REXCVAR_GET(native_renderer)) {
    Parallel::Get().SwapDone();
  }
}''')

r('''// The D3D library's occlusion query event (query type 9, sub_8258F810):
// writes RB_SAMPLE_COUNT_ADDR and EVENT_WRITE_ZPD; r4 = query, r5 = which of
// the two reports. With predicated tiling there is one report buffer per
// tile (query +144 = count, +24 = addresses). The native renderer measures
// the samples itself; the emulation no longer draws them.
extern "C" REX_FUNC(__imp__sub_8258EA28);
extern "C" REX_FUNC(sub_8258EA28) {
  const uint32_t query = ctx.r4.u32, second = ctx.r5.u32;
  __imp__sub_8258EA28(ctx, base);''',
  '''// The D3D library's occlusion query event: writes RB_SAMPLE_COUNT_ADDR and
// EVENT_WRITE_ZPD; r4 = query, r5 = which of the two reports. With predicated
// tiling there is one report buffer per tile (query +144 = count, +24 =
// addresses; the same layout as MW). The native renderer measures the samples
// itself; the emulation no longer draws them.
extern "C" REX_FUNC(__imp__sub_826ECC28);
extern "C" REX_FUNC(sub_826ECC28) {
  const uint32_t query = ctx.r4.u32, second = ctx.r5.u32;
  __imp__sub_826ECC28(ctx, base);''')

# Shader-embedded constants: Carbon's library loads them with
# LOAD_ALU_CONSTANT straight from memory into the GPU registers (sub_826FB970),
# not through the device's shadow; the recorder takes them from the packets of
# the shader load scan and lays them over the draw's registers.
r('''  std::vector<uint8_t> scanned_vs_code_;''',
  '''  std::vector<uint8_t> scanned_vs_code_;
  // Constants the last shader load scan saw loaded with LOAD_ALU_CONSTANT
  // (first shadow index | count << 16, then the values, big-endian), applied
  // at the next draw.
  std::vector<uint32_t> constant_loads_;''')
r('''  uint32_t load_address = 0, load_dwords = 0;''',
  '''  uint32_t load_address = 0, load_dwords = 0;
  std::vector<uint32_t> loads;''')
r('''        load_address = GuestToPhysical(p + 12);
        load_dwords = count - 2;
      }
    }
  }''',
  '''        load_address = GuestToPhysical(p + 12);
        load_dwords = count - 2;
      }
    } else if ((header & 0xC000FF00) == kAluConstantLoad && ((header >> 16) & 0x3FFF) == 2) {
      // LOAD_ALU_CONSTANT: physical address, type << 16 | first dword, dwords.
      // Type 0 (float constants, from register 0x4000) is what the library
      // loads for the shaders' own constants.
      const uint32_t address = LoadBE32(base + p + 4) & 0x1FFFFFFC;
      const uint32_t offset_type = LoadBE32(base + p + 8);
      const uint32_t dwords = LoadBE32(base + p + 12) & 0xFFF;
      const uint32_t first = offset_type & 0x7FF;
      auto* kernel = rex::system::kernel_state();
      const uint8_t* physical =
          kernel && kernel->memory() ? kernel->memory()->physical_membase() : nullptr;
      if (physical && ((offset_type >> 16) & 0xFF) == 0 && dwords && first + dwords <= 2048 &&
          uint64_t(address) + dwords * 4ull <= 0x20000000) {
        loads.push_back((kAluConstantsFlat + first) | (dwords << 16));
        const uint8_t* data = physical + address;
        for (uint32_t i = 0; i < dwords; ++i) {
          uint32_t value;
          std::memcpy(&value, data + 4 * i, 4);  // stays big-endian, as the shadow
          loads.push_back(value);
        }
      }
    }
  }''')
r('''  if (load_address) {
    keep(load_address, load_dwords);
  }
}''',
  '''  constant_loads_.insert(constant_loads_.end(), loads.begin(), loads.end());
  if (load_address) {
    keep(load_address, load_dwords);
  }
}''')
r('''constexpr uint32_t kImmediateLoad = 0xC0002B00;  // PM4 IM_LOAD_IMMEDIATE (count in 16:29)''',
  '''constexpr uint32_t kImmediateLoad = 0xC0002B00;  // PM4 IM_LOAD_IMMEDIATE (count in 16:29)
constexpr uint32_t kAluConstantLoad = 0xC0002F00;  // PM4 LOAD_ALU_CONSTANT
// Index of register 0x4000 (float constants) in the flat shadow.
constexpr uint32_t kAluConstantsFlat = 16 + 21 + 5 + 12 + 21 + 38 + 8;''')
r('''  pending_constants_dirty_[0] = pending_constants_dirty_[1] = 0;
  last_shadow_valid_ = true;''',
  '''  pending_constants_dirty_[0] = pending_constants_dirty_[1] = 0;
  last_shadow_valid_ = true;
  // The shader constants the draw's shader load put into the registers
  // directly, over the shadow's (they came after its constants).
  if (draw && !constant_loads_.empty()) {
    for (size_t i = 0; i < constant_loads_.size();) {
      const uint32_t header = constant_loads_[i++];
      const uint32_t flat = header & 0xFFFF, n = header >> 16;
      f.registers.push_back(header);
      f.registers.insert(f.registers.end(), constant_loads_.begin() + i,
                         constant_loads_.begin() + i + n);
      std::memcpy(last_shadow_.data() + flat, constant_loads_.data() + i, 4 * n);
      i += n;
    }
    constant_loads_.clear();
  }''')

r('''      // shader (sub_825A37D8): that copy is what runs.''', '''      // shader (MW: sub_825A37D8): that copy is what runs.''')

# NATIVE_DEBUG_FRAME=<n> (diagnostics): logs every draw of frame n.
r("""    d.stream0_stride_words = item.stream0_stride_words;""",
  """    d.stream0_stride_words = item.stream0_stride_words;
    if (debug_frame) {
      const uint32_t* fetch = &regs->values[XE_GPU_REG_SHADER_CONSTANT_FETCH_00_0];
      REXLOG_INFO(
          "[native debug] draw {} prim {} count {}{}{} vs {:016X} ps {:016X} | tex0 {:08X} {:08X} "
          "{:08X} | tex1 {:08X} {:08X} {:08X} | vf95 {:08X} {:08X}",
          item_index, item.primitive_type, item.count, item.indexed ? " indexed" : "",
          item.up ? " up" : "", d.vertex_shader_hash, d.pixel_shader_hash, fetch[0], fetch[1],
          fetch[2], fetch[6], fetch[7], fetch[8], fetch[190], fetch[191]);
    }""")
r("""  size_t item_index = 0;
  for (const Item& item : frame.items) {""",
  """  size_t item_index = 0;
  static const int debug_frame_wanted = [] {
    const char* v = std::getenv("NATIVE_DEBUG_FRAME");
    return v ? std::atoi(v) : -1;
  }();
  static int debug_frame_counter = 0;
  const bool debug_frame = debug_frame_counter++ == debug_frame_wanted;
  for (const Item& item : frame.items) {""")

# The front buffer: Carbon's swap gets it as a texture object (r4, fetch
# constant at +28); after its last resolve to the front buffer the frame
# resolves into other textures too, so MW's "last resolve" is wrong here.
r("""  void RecordOcclusion(const uint32_t* addresses, uint32_t count);""",
  """  void RecordOcclusion(const uint32_t* addresses, uint32_t count);
  void SetFrontBuffer(uint32_t physical) {
    std::lock_guard<std::mutex> lock(mutex_);
    recording_->front_buffer = physical;
  }""")
r("""// Swap: the frame is complete.
extern "C" REX_FUNC(sub_826E27A8) {
  __imp__sub_826E27A8(ctx, base);""",
  """// Swap (dev, front buffer texture, ...): the frame is complete.
extern "C" REX_FUNC(sub_826E27A8) {
  const uint32_t front = ctx.r4.u32;
  __imp__sub_826E27A8(ctx, base);
  if (REXCVAR_GET(native_renderer) && front) {
    Parallel::Get().SetFrontBuffer(
        GuestToPhysical(LoadBE32(base + front + 28 + 4) & 0xFFFFF000));
  }""")

# Pixel shaders from the scan too (IM_LOAD type 1: what the GPU loads), with
# counters of what the scans find.
r("""  uint32_t scanned_vs_ = 0, scanned_vs_object_ = 0, scanned_vs_dwords_ = 0;""",
  """  uint32_t scanned_vs_ = 0, scanned_vs_object_ = 0, scanned_vs_dwords_ = 0;
  // The last pixel shader load seen, and the device's pixel shader object then.
  uint32_t scanned_ps_ = 0, scanned_ps_object_ = 0;
  // Shader load scans, the loads they found, and pixel shaders whose load was
  // not where the object says.
  std::atomic<uint64_t> scans_{0}, scan_vs_loads_{0}, scan_ps_loads_{0}, scan_constant_loads_{0},
      ps_object_mismatch_{0};""")
r("""      if ((address_type & 3) == 0) {
        const uint32_t address = address_type & ~3u;
        load_address = address;
        load_dwords = 0;
      }""",
  """      if ((address_type & 3) == 0) {
        const uint32_t address = address_type & ~3u;
        load_address = address;
        load_dwords = 0;
      } else if ((address_type & 3) == 1) {
        ps_load_address = address_type & ~3u;
      }""")
r("""  uint32_t load_address = 0, load_dwords = 0;
  std::vector<uint32_t> loads;""",
  """  uint32_t load_address = 0, load_dwords = 0;
  uint32_t ps_load_address = 0;
  std::vector<uint32_t> loads;
  ++scans_;""")
r("""  constant_loads_.insert(constant_loads_.end(), loads.begin(), loads.end());
  if (load_address) {""",
  """  constant_loads_.insert(constant_loads_.end(), loads.begin(), loads.end());
  if (!loads.empty()) {
    ++scan_constant_loads_;
  }
  if (ps_load_address) {
    ++scan_ps_loads_;
    scanned_ps_ = ps_load_address;
    scanned_ps_object_ = LoadBE32(base + device + kDevicePixelShader);
  }
  if (load_address) {
    ++scan_vs_loads_;""")
r("""    if (ps_object) {
      // Microcode at ps[+24] + h[+40], h = ps + ps[+64].
      const uint32_t header = ps_object + LoadBE32(base + ps_object + 64);
      item.ps_code = AddCode(
          physical,
          GuestToPhysical(LoadBE32(base + ps_object + 24) + LoadBE32(base + header + 40)),
          item.ps_dwords, false);
    }""",
  """    if (ps_object) {
      // The load the scan saw for this object, else the object's microcode at
      // ps[+24] + h[+40], h = ps + ps[+64].
      const uint32_t header = ps_object + LoadBE32(base + ps_object + 64);
      uint32_t ps_address =
          GuestToPhysical(LoadBE32(base + ps_object + 24) + LoadBE32(base + header + 40));
      if (scanned_ps_ && scanned_ps_object_ == ps_object) {
        if (scanned_ps_ != ps_address) {
          ++ps_object_mismatch_;
        }
        ps_address = scanned_ps_;
      }
      item.ps_code = AddCode(physical, ps_address, item.ps_dwords, false);
    }""")
r("""      if (const uint64_t misaligned = walks_misaligned_.exchange(0)) {""",
  """      REXLOG_INFO("[native renderer] shader load scans in 10 s: {}, vertex shader loads {}, "
                  "pixel shader loads {}, with constant loads {}, pixel shaders not at the "
                  "object's address {}",
                  scans_.exchange(0), scan_vs_loads_.exchange(0), scan_ps_loads_.exchange(0),
                  scan_constant_loads_.exchange(0), ps_object_mismatch_.exchange(0));
      if (const uint64_t misaligned = walks_misaligned_.exchange(0)) {""")

r("""      c.dest_slice = item.slice;
      renderer.Resolve(c);""",
  """      c.dest_slice = item.slice;
      if (debug_frame) {
        REXLOG_INFO("[native debug] resolve {} to {:08X} ({:08X} {:08X}) rect {},{}-{},{}",
                    item_index, c.dest_fetch[1] & 0x1FFFF000, c.dest_fetch[0], c.dest_fetch[2],
                    c.rect[0], c.rect[1], c.rect[2], c.rect[3]);
      }
      renderer.Resolve(c);""")

# VGT_INDX_OFFSET: Carbon's draws write it into the command buffer only (MW's
# DrawVertices also kept it in the shadow): DrawVertices its start vertex,
# DrawIndexed and BeginVertices 0.
r("""    constant_loads_.clear();
  }""",
  """    constant_loads_.clear();
  }
  if (draw) {
    const uint32_t offset = entry == kEntryDrawVertices ? args[2] : 0;
    const uint32_t value = _byteswap_ulong(offset);  // big-endian, as the shadow
    if (last_shadow_[kIndexOffsetFlat] != value) {
      f.registers.push_back(kIndexOffsetFlat | (1u << 16));
      f.registers.push_back(value);
      last_shadow_[kIndexOffsetFlat] = value;
    }
  }""")
r("""constexpr uint32_t kAluConstantsFlat = 16 + 21 + 5 + 12 + 21 + 38 + 8;""",
  """constexpr uint32_t kAluConstantsFlat = 16 + 21 + 5 + 12 + 21 + 38 + 8;
// Index of VGT_INDX_OFFSET (0x2102) in the flat shadow.
constexpr uint32_t kIndexOffsetFlat = 16 + 2;""")

# NATIVE_STREAM_AUDIT=1 (diagnostics): walks every packet the D3D library
# writes into the command buffer and counts the register writes whose value
# is not what the device's shadow holds (state that bypasses the shadow, which
# the recorder does not see), and writes to registers outside the shadow.
r("""  void RecordOcclusion(const uint32_t* addresses, uint32_t count);""",
  """  void RecordOcclusion(const uint32_t* addresses, uint32_t count);
  void AuditStream(const uint8_t* base, uint32_t device, uint32_t from, uint32_t to,
                   bool at_draw);
  void LogAudit();
  void StreamWalk(const uint8_t* base, uint32_t from, uint32_t to, bool for_item);
  void StreamItemStart();
  void LogStreamState();""")
r("""namespace {

// Calls a hooked entry point and records it (MW: render_census.cpp).
template <void (*Original)(PPCContext&, uint8_t*)>
void RecordCall(int entry, PPCContext& ctx, uint8_t* base) {
  if (!REXCVAR_GET(native_renderer)) {
    Original(ctx, base);
    return;
  }
  const uint32_t args[8] = {ctx.r3.u32, ctx.r4.u32, ctx.r5.u32, ctx.r6.u32,
                            ctx.r7.u32, ctx.r8.u32, ctx.r9.u32, ctx.r10.u32};
  Parallel::Get().Before(entry, args, base);
  Original(ctx, base);
  Parallel::Get().Record(entry, args, ctx.r3.u32, base);
}

}  // namespace""",
  """namespace {

const bool g_stream_audit = std::getenv("NATIVE_STREAM_AUDIT") != nullptr;
// The audit and NATIVE_STREAM_STATE (Parallel::ApplyStreamState) walk the
// command buffer.
const bool g_stream_walk = g_stream_audit || std::getenv("NATIVE_STREAM_STATE") != nullptr;
// The last command buffer dword the walks took (this thread).
thread_local uint32_t t_audit_position = 0;
// Inside a recorded draw or resolve: a segment it starts ends part of it.
thread_local bool t_in_item = false;

void Walk(const uint8_t* base, uint32_t device, uint32_t from, uint32_t to, bool at_draw,
          bool for_item) {
  if (g_stream_audit) {
    Parallel::Get().AuditStream(base, device, from, to, at_draw);
  }
  Parallel::Get().StreamWalk(base, from, to, for_item);
}

// Calls a hooked entry point and records it (MW: render_census.cpp).
template <void (*Original)(PPCContext&, uint8_t*)>
void RecordCall(int entry, PPCContext& ctx, uint8_t* base) {
  if (!REXCVAR_GET(native_renderer)) {
    Original(ctx, base);
    return;
  }
  const uint32_t args[8] = {ctx.r3.u32, ctx.r4.u32, ctx.r5.u32, ctx.r6.u32,
                            ctx.r7.u32, ctx.r8.u32, ctx.r9.u32, ctx.r10.u32};
  const uint32_t device = args[0];
  const bool draw = entry == kEntryDrawIndexed || entry == kEntryDrawVertices ||
                    entry == kEntryBeginVertices;
  const bool item = draw || entry == kEntryResolve;
  if (g_stream_walk && entry == kEntrySegment && t_audit_position) {
    // The rest of the segment that ends now.
    Walk(base, device, t_audit_position, LoadBE32(base + device + kDeviceWritePointer), false,
         t_in_item);
    t_audit_position = 0;
  }
  if (g_stream_walk && item) {
    Parallel::Get().StreamItemStart();
    t_in_item = true;
  }
  Parallel::Get().Before(entry, args, base);
  Original(ctx, base);
  if (g_stream_walk) {
    if (entry == kEntrySegment) {
      t_audit_position = ctx.r3.u32;
    } else {
      const uint32_t now = LoadBE32(base + device + kDeviceWritePointer);
      if (t_audit_position) {
        Walk(base, device, t_audit_position, now, draw, item);
      }
      t_audit_position = now;
    }
    if (item) {
      t_in_item = false;
    }
  }
  // After the walks: with NATIVE_STREAM_STATE the item takes the register
  // writes they saw.
  Parallel::Get().Record(entry, args, ctx.r3.u32, base);
}

}  // namespace""")
r("""void Parallel::RecordOcclusion(const uint32_t* addresses, uint32_t count) {""",
  """namespace {
std::mutex g_audit_mutex;
std::map<uint32_t, uint64_t> g_audit_mismatch, g_audit_unshadowed, g_audit_written;
std::map<uint32_t, std::vector<std::pair<uint32_t, uint32_t>>> g_audit_samples;
uint64_t g_audit_packets = 0, g_audit_resets = 0;

// Device offset of a register's shadow, or 0 if it has none.
uint32_t ShadowOffset(uint32_t reg) {
  for (const ShadowGroup& g : kShadowGroups) {
    if (reg >= g.first_register && reg < g.first_register + g.count) {
      return g.device_offset + 4 * (reg - g.first_register);
    }
  }
  return 0;
}

constexpr uint16_t kNoFlat = 0xFFFF;
// Index of every register in the flat shadow (kNoFlat: not in the shadow).
const std::vector<uint16_t>& FlatIndexOfRegister() {
  static const std::vector<uint16_t> table = [] {
    std::vector<uint16_t> t(0x10000, kNoFlat);
    const auto& registers = ShadowRegisters();
    for (uint32_t flat = 0; flat < kShadowCount; ++flat) {
      t[registers[flat]] = uint16_t(flat);
    }
    return t;
  }();
  return table;
}

// Device offset of every dword of the flat shadow.
const std::array<uint16_t, kShadowCount>& ShadowDeviceOffsets() {
  static const std::array<uint16_t, kShadowCount> table = [] {
    std::array<uint16_t, kShadowCount> t = {};
    uint32_t flat = 0;
    for (const ShadowGroup& g : kShadowGroups) {
      for (uint32_t i = 0; i < g.count; ++i) {
        t[flat++] = uint16_t(g.device_offset + 4 * i);
      }
    }
    return t;
  }();
  return table;
}

// What WalkPackets reports.
enum class StreamEvent {
  kPacket,    // a packet header
  kWrite,     // register `reg` set to `value`
  kModify,    // REG_RMW: reg = (reg & mask) | value
  kUnknown,   // REG_RMW with register operands: the value is not known
  kDraw,      // DRAW_INDX(_2)(_BIN)
  kIndirect,  // INDIRECT_BUFFER(_PFD): commands elsewhere, not followed
};

// First register of SET_CONSTANT's and LOAD_ALU_CONSTANT's types: ALU, fetch,
// bool, loop, registers.
constexpr uint32_t kConstantBase[] = {0x4000, 0x4800, 0x4900, 0x4908, 0x2000};

// The packets the D3D library wrote into the command buffer after `from` up
// to `to` (write pointers: the last dword written), with the register writes
// as the command processor makes them (the SDK's
// CommandProcessor::ExecutePacketType*): on(event, reg, value, mask).
// LOAD_ALU_CONSTANT reads its values from memory now (as the shader load
// scan does).
template <typename F>
void WalkPackets(const uint8_t* base, const uint8_t* physical, uint32_t from, uint32_t to, F&& on) {
  for (uint32_t p = from + 4, next; p <= to; p = next) {
    const uint32_t header = LoadBE32(base + p);
    on(StreamEvent::kPacket, 0, header, 0);
    switch (header >> 30) {
      case 0: {
        // count values for registers from header & 0x7FFF (bit 15: all to it).
        const uint32_t count = ((header >> 16) & 0x3FFF) + 1;
        const uint32_t reg = header & 0x7FFF;
        const bool one_reg = (header >> 15) & 1;
        for (uint32_t i = 0; i < count && p + 4 + 4 * i <= to; ++i) {
          on(StreamEvent::kWrite, one_reg ? reg : reg + i, LoadBE32(base + p + 4 + 4 * i), 0);
        }
        next = p + 4 * (count + 1);
        break;
      }
      case 1:
        // Two registers (11 bits each).
        if (p + 8 <= to) {
          on(StreamEvent::kWrite, header & 0x7FF, LoadBE32(base + p + 4), 0);
          on(StreamEvent::kWrite, (header >> 11) & 0x7FF, LoadBE32(base + p + 8), 0);
        }
        next = p + 12;
        break;
      case 3: {
        const uint32_t count = ((header >> 16) & 0x3FFF) + 1;
        const uint32_t opcode = (header >> 8) & 0x7F;
        next = p + 4 * (count + 1);
        if (next > to + 4) {
          break;  // not written completely
        }
        auto dword = [&](uint32_t i) { return LoadBE32(base + p + 4 + 4 * i); };
        switch (opcode) {
          case 0x22:  // DRAW_INDX
          case 0x36:  // DRAW_INDX_2
          case 0x34:  // DRAW_INDX_BIN
          case 0x35:  // DRAW_INDX_2_BIN
            on(StreamEvent::kDraw, 0, 0, 0);
            break;
          case 0x2D:  // SET_CONSTANT: type << 16 | index, then the values
            if (count >= 2 && ((dword(0) >> 16) & 0xFF) < 5) {
              const uint32_t first = kConstantBase[(dword(0) >> 16) & 0xFF] + (dword(0) & 0x7FF);
              for (uint32_t i = 1; i < count; ++i) {
                on(StreamEvent::kWrite, first + i - 1, dword(i), 0);
              }
            }
            break;
          case 0x55:  // SET_CONSTANT2
          case 0x56:  // SET_SHADER_CONSTANTS: register index, then the values
            if (count >= 2) {
              const uint32_t first = dword(0) & 0xFFFF;
              for (uint32_t i = 1; i < count; ++i) {
                on(StreamEvent::kWrite, first + i - 1, dword(i), 0);
              }
            }
            break;
          case 0x2F:  // LOAD_ALU_CONSTANT: address, type << 16 | index, dwords
            if (count == 3 && physical && ((dword(1) >> 16) & 0xFF) < 5) {
              const uint32_t address = dword(0) & 0x1FFFFFFC;
              const uint32_t first = kConstantBase[(dword(1) >> 16) & 0xFF] + (dword(1) & 0x7FF);
              const uint32_t dwords = dword(2) & 0xFFF;
              if (uint64_t(address) + dwords * 4ull <= 0x20000000) {
                for (uint32_t i = 0; i < dwords; ++i) {
                  on(StreamEvent::kWrite, first + i, LoadBE32(physical + address + 4 * i), 0);
                }
              }
            }
            break;
          case 0x21:  // REG_RMW: register | flags, and mask, or mask
            if (count == 3) {
              if (dword(0) >> 30) {
                on(StreamEvent::kUnknown, dword(0) & 0x1FFF, 0, 0);
              } else {
                on(StreamEvent::kModify, dword(0) & 0x1FFF, dword(2), dword(1));
              }
            }
            break;
          case 0x3F:  // INDIRECT_BUFFER
          case 0x37:  // INDIRECT_BUFFER_PFD
            on(StreamEvent::kIndirect, 0, 0, 0);
            break;
          default:
            break;
        }
        break;
      }
      default:  // type 2: no-op
        next = p + 4;
        break;
    }
  }
}

const uint8_t* PhysicalMemory() {
  auto* kernel = rex::system::kernel_state();
  return kernel && kernel->memory() ? kernel->memory()->physical_membase() : nullptr;
}
}  // namespace

// NATIVE_STREAM_STATE=<mask> (1 draws, 2 resolves, 3 both): Carbon's D3D
// library writes some state into the command buffer only, not into the
// device's register shadow the recorder reads (NATIVE_STREAM_AUDIT: the vertex
// fetch constants of the streams 0x48BA-0x48BF, ...). The walks of what it
// wrote since the previous item (RecordCall) collect the register writes; at
// the item those up to its last draw packet are laid over the shadow (the
// later ones are for the next item). A register keeps the command buffer's
// value until the command buffer writes it again or the shadow changes (a Set
// call the command buffer did not show yet). Only registers of the shadow
// groups; NATIVE_STREAM_STATE_REGISTERS=<hex>[-<hex>],... narrows them (for
// finding out which ones matter).
void Parallel::StreamItemStart() {
  if (!stream_state_) {
    return;
  }
  std::lock_guard<std::mutex> lock(mutex_);
  stream_draw_mark_ = -1;
}

void Parallel::StreamWalk(const uint8_t* base, uint32_t from, uint32_t to, bool for_item) {
  if (!stream_state_) {
    return;
  }
  std::lock_guard<std::mutex> lock(mutex_);
  if (to < from || to - from > (1u << 20) || stream_writes_.size() > (1u << 20)) {
    // Not one segment, or no item took the writes: the state is not known.
    stream_writes_.clear();
    stream_draw_mark_ = -1;
    stream_lost_ = true;
    ++stream_lost_walks_;
    return;
  }
  const auto& flat_of = FlatIndexOfRegister();
  WalkPackets(base, PhysicalMemory(), from, to,
              [&](StreamEvent event, uint32_t reg, uint32_t value, uint32_t mask) {
                switch (event) {
                  case StreamEvent::kWrite:
                  case StreamEvent::kModify:
                  case StreamEvent::kUnknown: {
                    const uint16_t flat = flat_of[reg & 0xFFFF];
                    if (flat == kNoFlat) {
                      ++stream_unshadowed_;
                    } else if (stream_allowed_[flat]) {
                      stream_writes_.push_back({flat, uint8_t(event), value, mask});
                    }
                    break;
                  }
                  case StreamEvent::kDraw:
                    if (for_item) {
                      stream_draw_mark_ = int64_t(stream_writes_.size());
                    }
                    break;
                  case StreamEvent::kIndirect:
                    ++stream_indirect_;
                    break;
                  default:
                    break;
                }
              });
}

void Parallel::ApplyStreamState(Frame& f, const uint8_t* device) {
  const auto& offsets = ShadowDeviceOffsets();
  // Values big-endian, as in the shadow and last_shadow_.
  auto shadow = [&](uint32_t flat) {
    uint32_t value;
    std::memcpy(&value, device + offsets[flat], 4);
    return value;
  };
  auto set = [&](uint32_t flat, uint32_t value) {
    if (last_shadow_[flat] != value) {
      f.registers.push_back(flat | (1u << 16));
      f.registers.push_back(value);
      last_shadow_[flat] = value;
    }
  };
  if (stream_lost_) {
    // A walk was lost: the shadow's values until the command buffer sets them.
    for (uint16_t flat : stream_active_) {
      stream_registers_[flat].active = false;
      set(flat, shadow(flat));
    }
    stream_active_.clear();
    stream_lost_ = false;
  }
  // The writes up to the item's draw packet, in order.
  const size_t taken = stream_draw_mark_ >= 0
                           ? std::min(size_t(stream_draw_mark_), stream_writes_.size())
                           : stream_writes_.size();
  for (size_t i = 0; i < taken; ++i) {
    const StreamWrite& w = stream_writes_[i];
    StreamRegister& r = stream_registers_[w.flat];
    if (!r.touched) {
      r.touched = true;
      r.unknown = false;
      r.next = r.active ? r.value : shadow(w.flat);
      stream_touched_.push_back(w.flat);
    }
    switch (StreamEvent(w.event)) {
      case StreamEvent::kWrite:
        r.next = _byteswap_ulong(w.value);
        r.unknown = false;
        break;
      case StreamEvent::kModify:
        r.next = _byteswap_ulong((_byteswap_ulong(r.next) & w.mask) | w.value);
        break;
      default:
        r.unknown = true;
        ++stream_unknown_;
        break;
    }
  }
  stream_writes_.erase(stream_writes_.begin(), stream_writes_.begin() + taken);
  stream_draw_mark_ = -1;
  for (uint16_t flat : stream_touched_) {
    StreamRegister& r = stream_registers_[flat];
    r.touched = false;
    const uint32_t now = shadow(flat);
    if (r.unknown || r.next == now) {
      // The shadow's value (the inactive entry leaves stream_active_ below).
      r.active = false;
      set(flat, now);
    } else {
      if (!r.active) {
        r.active = true;
        stream_active_.push_back(flat);
      }
      r.value = r.next;
      r.shadow = now;
    }
  }
  stream_touched_.clear();
  // Over the shadow, unless the shadow changed since.
  size_t kept = 0;
  for (uint16_t flat : stream_active_) {
    StreamRegister& r = stream_registers_[flat];
    if (!r.active) {
      continue;
    }
    const uint32_t now = shadow(flat);
    if (now != r.shadow) {
      r.active = false;
      set(flat, now);
      continue;
    }
    set(flat, r.value);
    ++stream_override_counts_[flat];
    stream_active_[kept++] = flat;
  }
  stream_active_.resize(kept);
  ++stream_items_;
  if (kept) {
    ++stream_items_overridden_;
  }
}

void Parallel::LogStreamState() {
  std::lock_guard<std::mutex> lock(mutex_);
  const auto& registers = ShadowRegisters();
  std::vector<std::pair<uint32_t, uint32_t>> top;
  for (uint32_t flat = 0; flat < kShadowCount; ++flat) {
    if (stream_override_counts_[flat]) {
      top.push_back({stream_override_counts_[flat], flat});
    }
  }
  std::sort(top.rbegin(), top.rend());
  std::string out;
  for (size_t i = 0; i < top.size() && i < 24; ++i) {
    const uint32_t flat = top[i].second;
    const StreamRegister& r = stream_registers_[flat];
    char buf[64];
    std::snprintf(buf, sizeof(buf), " %04X:%u", registers[flat], top[i].first);
    out += buf;
    if (r.active) {
      std::snprintf(buf, sizeof(buf), "(%08X/%08X)", _byteswap_ulong(r.value),
                    _byteswap_ulong(r.shadow));
      out += buf;
    }
  }
  REXLOG_INFO("[native stream state] 10 s: {} of {} items with registers from the command "
              "buffer, {} now | writes outside the shadow {}, REG_RMW unknown {}, indirect "
              "buffers {}, walks lost {} | register:items(command buffer/shadow now):{}",
              stream_items_overridden_, stream_items_, stream_active_.size(),
              stream_unshadowed_, stream_unknown_, stream_indirect_, stream_lost_walks_, out);
  stream_override_counts_.fill(0);
  stream_items_ = stream_items_overridden_ = stream_unshadowed_ = stream_unknown_ =
      stream_indirect_ = stream_lost_walks_ = 0;
}

void Parallel::AuditStream(const uint8_t* base, uint32_t device, uint32_t from, uint32_t to,
                           bool at_draw) {
  if (to < from || to - from > (1u << 20)) {
    std::lock_guard<std::mutex> lock(g_audit_mutex);
    ++g_audit_resets;
    return;
  }
  std::lock_guard<std::mutex> lock(g_audit_mutex);
  // Registers as the command stream leaves them (GPU state), compared with
  // the shadow at the last draw packet of a recorded draw.
  static std::vector<uint32_t> stream(0x10000);
  static std::vector<uint8_t> known(0x10000);
  auto value_written = [&](uint32_t reg, uint32_t value) {
    reg &= 0xFFFF;
    ++g_audit_written[reg];
    stream[reg] = value;
    known[reg] = 1;
    if (!ShadowOffset(reg)) {
      ++g_audit_unshadowed[reg];
    }
  };
  bool drew = false;
  // NATIVE_STREAM_DUMP=<n>: the raw dwords of the n-th walk at a draw, once.
  static int dump_at = [] {
    const char* v = std::getenv("NATIVE_STREAM_DUMP");
    return v ? std::atoi(v) : -1;
  }();
  if (at_draw && dump_at >= 0 && dump_at-- == 0) {
    std::string out;
    for (uint32_t q = from + 4; q <= to && q < from + 4 + 4 * 400; q += 4) {
      char buf[16];
      std::snprintf(buf, sizeof(buf), " %08X", LoadBE32(base + q));
      out += buf;
    }
    REXLOG_INFO("[native audit] stream {:08X}-{:08X}:{}", from + 4, to, out);
  }
  // (SET_CONSTANT2 and SET_SHADER_CONSTANTS take a register index, not
  // SET_CONSTANT's type and index; REG_RMW and LOAD_ALU_CONSTANT count too.)
  WalkPackets(base, PhysicalMemory(), from, to,
              [&](StreamEvent event, uint32_t reg, uint32_t value, uint32_t mask) {
                switch (event) {
                  case StreamEvent::kPacket:
                    ++g_audit_packets;
                    break;
                  case StreamEvent::kWrite:
                    value_written(reg, value);
                    break;
                  case StreamEvent::kModify:
                    if (known[reg & 0xFFFF]) {
                      value_written(reg, (stream[reg & 0xFFFF] & mask) | value);
                    }
                    break;
                  case StreamEvent::kUnknown:
                    known[reg & 0xFFFF] = 0;
                    break;
                  case StreamEvent::kDraw:
                    drew = true;
                    break;
                  default:
                    break;
                }
              });
  if (at_draw && drew) {
    for (const ShadowGroup& g : kShadowGroups) {
      for (uint32_t i = 0; i < g.count; ++i) {
        const uint32_t reg = g.first_register + i;
        const uint32_t shadow = LoadBE32(base + device + g.device_offset + 4 * i);
        if (known[reg] && stream[reg] != shadow) {
          ++g_audit_mismatch[reg];
          auto& samples = g_audit_samples[reg];
          if (samples.size() < 4) {
            samples.push_back({stream[reg], shadow});
          }
        }
      }
    }
  }
}

void Parallel::LogAudit() {
  std::lock_guard<std::mutex> lock(g_audit_mutex);
  auto top = [](const std::map<uint32_t, uint64_t>& m) {
    std::vector<std::pair<uint64_t, uint32_t>> v;
    for (const auto& [reg, n] : m) v.push_back({n, reg});
    std::sort(v.rbegin(), v.rend());
    std::string out;
    for (size_t i = 0; i < v.size() && i < 30; ++i) {
      char buf[32];
      std::snprintf(buf, sizeof(buf), " %04X:%llu", v[i].second, (unsigned long long)v[i].first);
      out += buf;
    }
    return out;
  };
  REXLOG_INFO("[native audit] {} packets, {} walks dropped | at draws, not as in the shadow:{}",
              g_audit_packets, g_audit_resets, top(g_audit_mismatch));
  REXLOG_INFO("[native audit] registers without a shadow:{}", top(g_audit_unshadowed));
  std::vector<std::pair<uint64_t, uint32_t>> worst;
  for (const auto& [reg, n] : g_audit_mismatch) worst.push_back({n, reg});
  std::sort(worst.rbegin(), worst.rend());
  if (worst.size() > 24) worst.resize(24);
  for (const auto& [count, reg] : worst) {
    std::string out;
    for (const auto& [stream, shadow] : g_audit_samples[reg]) {
      char buf[48];
      std::snprintf(buf, sizeof(buf), " %08X/%08X", stream, shadow);
      out += buf;
    }
    REXLOG_INFO("[native audit] {:04X} stream/shadow:{}", reg, out);
  }
  g_audit_samples.clear();
  g_audit_mismatch.clear();
  g_audit_unshadowed.clear();
  g_audit_written.clear();
  g_audit_packets = g_audit_resets = 0;
}

void Parallel::RecordOcclusion(const uint32_t* addresses, uint32_t count) {""")
r("""      REXLOG_INFO("[native renderer] shader load scans in 10 s: {}, vertex shader loads {}, \"""",
  """      if (std::getenv("NATIVE_STREAM_AUDIT")) {
        LogAudit();
      }
      if (stream_state_) {
        LogStreamState();
      }
      REXLOG_INFO("[native renderer] shader load scans in 10 s: {}, vertex shader loads {}, \"""")

# NATIVE_STREAM_STATE (see Parallel::ApplyStreamState): the registers Carbon's
# library writes into the command buffer only, laid over the shadow.
r("""// Index of VGT_INDX_OFFSET (0x2102) in the flat shadow.
constexpr uint32_t kIndexOffsetFlat = 16 + 2;""",
  """// Index of VGT_INDX_OFFSET (0x2102) in the flat shadow.
constexpr uint32_t kIndexOffsetFlat = 16 + 2;
// Index of fetch constant 95 (0x48BE, stream 0) in the flat shadow.
constexpr uint32_t kFetch95Flat = kAluConstantsFlat + 2048 + 190;
static_assert(kDeviceFetch95 == 1024 + 4 * 190, "fetch constant 95 in the 0x4800 group");

// NATIVE_STREAM_STATE_REGISTERS=<hex>[-<hex>],...: the registers
// NATIVE_STREAM_STATE takes from the command buffer (all of the shadow's
// without it).
std::vector<bool> StreamAllowed() {
  const auto& registers = ShadowRegisters();
  const char* v = std::getenv("NATIVE_STREAM_STATE_REGISTERS");
  std::vector<bool> allowed(kShadowCount, v == nullptr);
  for (const char* p = v; p && *p;) {
    char* end;
    const unsigned long first = std::strtoul(p, &end, 16);
    if (end == p) {
      break;
    }
    unsigned long last = first;
    p = end;
    if (*p == '-') {
      last = std::strtoul(p + 1, &end, 16);
      p = end;
    }
    for (uint32_t flat = 0; flat < kShadowCount; ++flat) {
      if (registers[flat] >= first && registers[flat] <= last) {
        allowed[flat] = true;
      }
    }
    while (*p == ',' || *p == ' ') {
      ++p;
    }
  }
  return allowed;
}""")
r("""  uint64_t scanned_vs_hash_ = 0;""",
  """  uint64_t scanned_vs_hash_ = 0;
  // NATIVE_STREAM_STATE (mask: 1 draws, 2 resolves; mutex_ held): the
  // register writes the walks saw that no item took yet (value and mask as
  // read, event a StreamEvent), the end of those before the current item's
  // last draw packet (-1: none seen), and per register of the shadow the
  // command buffer's value where it differs from the shadow's (big-endian).
  void ApplyStreamState(Frame& f, const uint8_t* device);
  const int stream_state_ = [] {
    const char* v = std::getenv("NATIVE_STREAM_STATE");
    return v ? std::atoi(v) & 3 : 0;
  }();
  struct StreamWrite {
    uint16_t flat;
    uint8_t event;
    uint32_t value, mask;
  };
  std::vector<StreamWrite> stream_writes_;
  int64_t stream_draw_mark_ = -1;
  struct StreamRegister {
    // The command buffer's value, and the shadow's when it was written.
    uint32_t value = 0, shadow = 0;
    // While an item takes the writes.
    uint32_t next = 0;
    bool active = false, touched = false, unknown = false;
  };
  std::array<StreamRegister, kShadowCount> stream_registers_ = {};
  std::vector<uint16_t> stream_active_, stream_touched_;
  // A walk was lost (the write pointer moved to another segment unseen).
  bool stream_lost_ = false;
  const std::vector<bool> stream_allowed_ = StreamAllowed();
  // For the log every 10 s.
  std::array<uint32_t, kShadowCount> stream_override_counts_ = {};
  uint64_t stream_items_ = 0, stream_items_overridden_ = 0, stream_unshadowed_ = 0,
           stream_unknown_ = 0, stream_indirect_ = 0, stream_lost_walks_ = 0;""")
r("""      last_shadow_[kIndexOffsetFlat] = value;
    }
  }
  if (draw) {
    item.primitive_type = args[1];""",
  """      last_shadow_[kIndexOffsetFlat] = value;
    }
  }
  // NATIVE_STREAM_STATE: the registers the library wrote into the command
  // buffer only.
  if (stream_state_ & (draw ? 1 : 2)) {
    ApplyStreamState(f, device);
  }
  if (draw) {
    item.primitive_type = args[1];""")

for old, new in R:
    c = t.count(old)
    if c != 1:
        sys.exit(f"anchor count {c}: {old[:100]!r}")
    t = t.replace(old, new, 1)
for bad in ("825A3AF0", "8258EA28", "kDeviceStreams ", "kDeviceVertexDeclaration", "kEntryFlush",
            "NFSMW_DUMP"):
    if bad in t:
        print("still contains", bad)
open(sys.argv[2], "w", encoding="utf-8", newline="").write(t.replace("\n", "\r\n") if crlf else t)
print("ok", len(R), "edits")
