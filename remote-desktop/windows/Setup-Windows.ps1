$ErrorActionPreference = 'Stop'
try {
    $exe = Join-Path $PSScriptRoot 'rustdesk-1.5.0-x86_64.exe'
    $expected = '8555777215510d83d2d61c9dc984e4fcc838bd7e79f9d18a42585431f5e8bb47'
    if ((Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
        throw 'The RustDesk installer checksum does not match. Download a fresh setup package.'
    }
    $settings = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'server-settings.json') | ConvertFrom-Json
    Set-Clipboard -Value $settings.importCode
    Unblock-File -LiteralPath $exe
    Start-Process notepad.exe -ArgumentList ('"' + (Join-Path $PSScriptRoot 'READ-ME.txt') + '"')
    Start-Process -FilePath $exe
    Write-Host 'RustDesk opened. Choose Install to enable its Windows startup service.'
    Write-Host 'Your private server import code is on the clipboard. Follow READ-ME.txt.'
} catch {
    Write-Error $_
    exit 1
}
