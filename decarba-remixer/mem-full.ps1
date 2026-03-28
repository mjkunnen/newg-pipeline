# Current commit charge
$perf = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
$commitGB = [math]::Round([long]$perf.CommittedBytes/1GB,1)
Write-Host "=== Commit Charge: $commitGB GB ==="
Write-Host ""

# Process private bytes total
$totalPriv = [math]::Round((Get-Process | Measure-Object PrivateMemorySize64 -Sum).Sum/1GB,1)
Write-Host "Process Private Bytes: $totalPriv GB"

# Kernel pools
$nonpaged = [math]::Round([long]$perf.PoolNonpagedBytes/1MB)
$paged = [math]::Round([long]$perf.PoolPagedBytes/1MB)
Write-Host "Kernel Nonpaged Pool:  $nonpaged MB"
Write-Host "Kernel Paged Pool:     $paged MB"
Write-Host ""

# Driver memory (often hidden commit)
Write-Host "=== Top drivers by memory ==="
$drivers = Get-CimInstance Win32_SystemDriver | Where-Object { $_.State -eq 'Running' }
Write-Host "Running drivers: $($drivers.Count)"
Write-Host ""

# Check for large memory-mapped files / shared sections
Write-Host "=== Page file usage ==="
Get-CimInstance Win32_PageFileUsage | ForEach-Object {
    Write-Host "  $($_.Name): $($_.CurrentUsage) MB used of $($_.AllocatedBaseSize) MB"
}
Write-Host ""

# GPU committed memory
Write-Host "=== GPU Memory ==="
$gpus = Get-CimInstance Win32_VideoController
foreach ($g in $gpus) {
    $vram = [math]::Round($g.AdapterRAM/1MB)
    Write-Host "  $($g.Name): $vram MB VRAM, Status=$($g.Status)"
}
Write-Host ""

# Shared memory sections - check for big ones
Write-Host "=== Mapped/Shared memory estimate ==="
$totalWS = (Get-Process | Measure-Object WorkingSet64 -Sum).Sum
$totalPrivWS = (Get-Process | Measure-Object PrivateMemorySize64 -Sum).Sum
$os = Get-CimInstance Win32_OperatingSystem
$totalRAM = $os.TotalVisibleMemorySize * 1KB
$freeRAM = $os.FreePhysicalMemory * 1KB
$usedRAM = $totalRAM - $freeRAM

Write-Host "  Physical used:     $([math]::Round($usedRAM/1GB,1)) GB"
Write-Host "  Process WS total:  $([math]::Round($totalWS/1GB,1)) GB"
Write-Host "  Standby/cached:    check below"
Write-Host ""

# Detailed memory counters
Write-Host "=== Memory Breakdown ==="
Write-Host "  Available:         $([math]::Round([long]$perf.AvailableBytes/1GB,1)) GB"
Write-Host "  Cache Bytes:       $([math]::Round([long]$perf.CacheBytes/1MB)) MB"
Write-Host "  Modified Pages:    $([math]::Round([long]$perf.ModifiedPageListBytes/1MB)) MB"
Write-Host "  Standby Cache:     $([math]::Round([long]$perf.StandbyCacheCoreBytes/1GB + [long]$perf.StandbyCacheNormalPriorityBytes/1GB + [long]$perf.StandbyCacheReserveBytes/1GB,1)) GB"
Write-Host ""

# Summary
$kernelMB = $nonpaged + $paged
$accountedGB = [math]::Round($totalPrivWS/1GB + $kernelMB/1024, 1)
$unaccounted = [math]::Round($commitGB - $accountedGB, 1)
Write-Host "=== SUMMARY ==="
Write-Host "  Total Committed:       $commitGB GB"
Write-Host "  Process Private:       $totalPriv GB"
Write-Host "  Kernel Pools:          $([math]::Round($kernelMB/1024,1)) GB"
Write-Host "  UNACCOUNTED:           $unaccounted GB"
Write-Host "  (likely: GPU shared mem, AWE, large page file mappings, driver allocations)"
