param(
    [Parameter(Mandatory=$true)][string]$Python,
    [Parameter(Mandatory=$true)][string]$Config,
    [Parameter(Mandatory=$true)][string]$Output
)
$ErrorActionPreference = 'Stop'
$collectorScript = (Join-Path $PSScriptRoot 'collector.py')
$pythonExe = (Resolve-Path -LiteralPath $Python).Path
$configFile = (Resolve-Path -LiteralPath $Config).Path
$outputFolder = [System.IO.Path]::GetFullPath($Output)
if (-not (Test-Path -LiteralPath $outputFolder)) {
    New-Item -ItemType Directory -Path $outputFolder | Out-Null
}
$taskName = 'CleanUIChromecastDiagnostics'
$oldTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($oldTask -and $oldTask.Description -ne 'Private read-only Clean UI Chromecast diagnostics') {
    throw 'An unrelated task already uses this name; nothing changed.'
}
$account = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$acl = Get-Acl -LiteralPath $outputFolder
$acl.SetAccessRuleProtection($true, $false)
foreach ($identity in @([System.Security.Principal.NTAccount]::new($account), [System.Security.Principal.SecurityIdentifier]::new('S-1-5-18'), [System.Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))) {
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        $identity, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
    $acl.AddAccessRule($rule)
}
Set-Acl -LiteralPath $outputFolder -AclObject $acl
# Config contains the paired identifier and private path, not an OTP or ADB key.
$configAcl = Get-Acl -LiteralPath (Split-Path -Parent $configFile)
$configAcl.SetAccessRuleProtection($true, $false)
foreach ($identity in @([System.Security.Principal.NTAccount]::new($account), [System.Security.Principal.SecurityIdentifier]::new('S-1-5-18'), [System.Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))) {
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        $identity, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
    $configAcl.AddAccessRule($rule)
}
Set-Acl -LiteralPath (Split-Path -Parent $configFile) -AclObject $configAcl
$arguments = '"{0}" --config "{1}" --output "{2}"' -f $collectorScript,$configFile,$outputFolder
$action = New-ScheduledTaskAction -Execute $pythonExe -Argument $arguments -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $account
$principal = New-ScheduledTaskPrincipal -UserId $account -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -StartWhenAvailable
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Private read-only Clean UI Chromecast diagnostics' -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Output 'Private collector installed; waits for the paired Chromecast without opening a window.'
