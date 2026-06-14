$ports = 8501..8510
$listeners = @()

foreach ($line in netstat -ano) {
    if ($line -notmatch "LISTENING") {
        continue
    }

    foreach ($port in $ports) {
        if ($line -match "[:.]$port\s") {
            $parts = $line -split "\s+" | Where-Object { $_ }
            if ($parts.Count -ge 5) {
                $listeners += [PSCustomObject]@{
                    Port = $port
                    PID = [int]$parts[-1]
                }
            }
        }
    }
}

$listeners = $listeners | Sort-Object Port, PID -Unique

if (-not $listeners) {
    Write-Host "No Streamlit-like listeners found on ports 8501-8510."
    exit 0
}

Write-Host "Found listeners on ports 8501-8510:"
foreach ($listener in $listeners) {
    $process = Get-Process -Id $listener.PID -ErrorAction SilentlyContinue
    $name = if ($process) { $process.ProcessName } else { "unknown" }
    Write-Host ("Port {0}: PID {1} ({2})" -f $listener.Port, $listener.PID, $name)
}

$answer = Read-Host "Stop these processes? Type Y to continue"
if ($answer -notin @("Y", "y")) {
    Write-Host "No processes stopped."
    exit 0
}

$pids = $listeners | Select-Object -ExpandProperty PID -Unique
foreach ($pidToStop in $pids) {
    try {
        Stop-Process -Id $pidToStop -Force -ErrorAction Stop
        Write-Host ("Stopped PID {0}." -f $pidToStop)
    }
    catch {
        Write-Host ("Could not stop PID {0}: {1}" -f $pidToStop, $_.Exception.Message)
    }
}
