param(
    [string]$QtDir = ""
)

# Builds the Qt launcher into launcher-windows\out\NFS_Carbon.exe and copies
# the Qt DLLs it needs next to it (windeployqt). From the source tree it finds
# the game in out\build\win-amd64-vk\ (see LauncherWindow::locate).
#
# Needs Qt 6 for MSVC 2022 x64 (-QtDir, $env:QT_DIR, or D:\Qt\6.*\msvc2022_64,
# C:\Qt\6.*\msvc2022_64). Qt's MSVC binaries need the MSVC compiler, not clang.

$ErrorActionPreference = "Stop"

$here = $PSScriptRoot
$out = Join-Path $here "out"

if (-not $QtDir) { $QtDir = $env:QT_DIR }
if (-not $QtDir) {
    $QtDir = Get-ChildItem "D:\Qt\6.*\msvc2022_64", "C:\Qt\6.*\msvc2022_64" -Directory -ErrorAction SilentlyContinue |
        Where-Object { Test-Path (Join-Path $_.FullName "lib\cmake\Qt6\Qt6Config.cmake") } |
        Sort-Object FullName | Select-Object -Last 1 -ExpandProperty FullName
}
if (-not $QtDir) { throw "Qt 6 for MSVC 2022 x64 not found (pass -QtDir or set QT_DIR)" }
Write-Output "Qt: $QtDir"

$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (-not (Test-Path -LiteralPath $vswhere)) { throw "vswhere not found; install VS 2022 Build Tools" }
$vsPath = & $vswhere -latest -products * -property installationPath
& (Join-Path $vsPath "Common7\Tools\Launch-VsDevShell.ps1") -Arch amd64 -HostArch amd64 -SkipAutomaticLocation | Out-Null

cmake -S $here -B $out -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=cl "-DCMAKE_PREFIX_PATH=$QtDir"
if ($LASTEXITCODE -ne 0) { throw "CMake configure failed ($LASTEXITCODE)" }
cmake --build $out
if ($LASTEXITCODE -ne 0) { throw "CMake build failed ($LASTEXITCODE)" }

& (Join-Path $QtDir "bin\windeployqt.exe") --release --no-translations --no-system-d3d-compiler `
    --no-opengl-sw --no-compiler-runtime --no-quick-import --no-network (Join-Path $out "NFS_Carbon.exe")
if ($LASTEXITCODE -ne 0) { throw "windeployqt failed ($LASTEXITCODE)" }

Write-Output "Launcher ready: $(Join-Path $out 'NFS_Carbon.exe')"
