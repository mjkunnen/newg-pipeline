# GPU shared memory from registry
Write-Host "=== GPU Dedicated + Shared Memory ==="
$adapters = Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\0*" -ErrorAction SilentlyContinue
foreach ($a in $adapters) {
    if ($a.DriverDesc) {
        $dedicated = if ($a.HardwareInformation.qwMemorySize) { [math]::Round([long]$a.'HardwareInformation.qwMemorySize'/1GB,1) } else { "?" }
        Write-Host "  $($a.DriverDesc): Dedicated=$dedicated GB"
    }
}
Write-Host ""

# Use dxdiag-like info
Write-Host "=== GPU Shared System Memory (from WMI) ==="
Get-CimInstance Win32_VideoController | ForEach-Object {
    Write-Host "  $($_.Name)"
    Write-Host "    AdapterRAM:     $([math]::Round($_.AdapterRAM/1MB)) MB"
    Write-Host "    SharedSystemMem: $([math]::Round($_.AdapterDACType))"
}
Write-Host ""

# Check for large virtual address space consumers
Write-Host "=== Top 20 by Virtual Size (includes shared/mapped) ==="
Get-Process | Sort-Object VirtualMemorySize64 -Descending | Select-Object -First 20 Name, Id, @{N='VirtualGB';E={[math]::Round($_.VirtualMemorySize64/1GB,1)}}, @{N='PrivateMB';E={[math]::Round($_.PrivateMemorySize64/1MB)}}, @{N='WSMB';E={[math]::Round($_.WorkingSet64/1MB)}} | Format-Table -AutoSize
Write-Host ""

# Hyper-V / WSL memory
Write-Host "=== Hyper-V / WSL / Docker ==="
$hvService = Get-Service vmcompute -ErrorAction SilentlyContinue
if ($hvService) { Write-Host "  vmcompute (Hyper-V): $($hvService.Status)" } else { Write-Host "  Hyper-V compute: not found" }
$wsl = Get-Service LxssManager -ErrorAction SilentlyContinue
if ($wsl) { Write-Host "  WSL (LxssManager): $($wsl.Status)" } else { Write-Host "  WSL: not found" }
$docker = Get-Process -Name "com.docker*" -ErrorAction SilentlyContinue
if ($docker) { Write-Host "  Docker: running ($($docker.Count) procs)" } else { Write-Host "  Docker: not running" }
Write-Host ""

# Vmmem process (WSL/Hyper-V VM memory)
$vmmem = Get-Process -Name "vmmem*" -ErrorAction SilentlyContinue
if ($vmmem) {
    $vmmemMB = [math]::Round(($vmmem | Measure-Object WorkingSet64 -Sum).Sum/1MB)
    Write-Host "  vmmem process: $vmmemMB MB (THIS IS LIKELY YOUR MISSING MEMORY)"
} else {
    Write-Host "  vmmem: not running"
}
