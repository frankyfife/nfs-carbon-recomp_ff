param([string]$Log, [string]$Front, [string]$Extra = "", [int]$Seconds = 60, [string[]]$Keys = @("ESC@20"))
# Starts the game with the native renderer, sends key presses to its window
# (name@second), saves the native front buffer and stops it after $Seconds.
Add-Type @"
using System; using System.Runtime.InteropServices;
public class K {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
}
"@
$vk = @{ ESC = 0x1B; ENTER = 0x0D; SPACE = 0x20; UP = 0x26; DOWN = 0x28; LEFT = 0x25; RIGHT = 0x27; W = 0x57 }
$d = "D:\recomp games\nfscarbon\nfs-carbon-recomp_ff\out\build\win-amd64-vk"
$env:NATIVE_SAVE_FRONT = $Front
$argStr = "--log_file=`"$Log`" --gpu_plugin=xenos --gpu_backend=d3d12 --native_renderer=true --fullscreen=false --resolution=720p $Extra"
$p = Start-Process -FilePath "$d\nfscarbon.exe" -ArgumentList $argStr -WorkingDirectory $d -PassThru
$events = $Keys | ForEach-Object { $k, $t = $_ -split "@"; [pscustomobject]@{ Key = $k; At = [double]$t } } | Sort-Object At
$start = Get-Date
foreach ($e in $events) {
  $wait = $e.At - ((Get-Date) - $start).TotalSeconds
  if ($wait -gt 0) { Start-Sleep -Milliseconds ([int]($wait * 1000)) }
  $p.Refresh()
  [K]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
  Start-Sleep -Milliseconds 150
  $code = [byte]$vk[$e.Key]
  [K]::keybd_event($code, 0, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 120
  [K]::keybd_event($code, 0, 2, [UIntPtr]::Zero)
  "key $($e.Key) at $([int]((Get-Date) - $start).TotalSeconds)s"
}
$rest = $Seconds - ((Get-Date) - $start).TotalSeconds
if ($rest -gt 0) { Start-Sleep -Seconds ([int]$rest) }
if (-not $p.HasExited) { $p | Stop-Process -Force; "stopped" } else { "exited $($p.ExitCode)" }
