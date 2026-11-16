"""Windows toast notifications and shared proactive message queue."""
import subprocess


def send_windows_notification(title: str, message: str):
    """Send a Windows balloon/toast notification via PowerShell."""
    safe_msg = message.replace('"', "'").replace("\n", " ")
    safe_title = title.replace('"', "'")
    script = f"""
Add-Type -AssemblyName System.Windows.Forms
$global:balloon = New-Object System.Windows.Forms.NotifyIcon
$path = (Get-Process -id $pid).Path
$balloon.Icon = [System.Drawing.Icon]::ExtractAssociatedIcon($path)
$balloon.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::None
$balloon.BalloonTipText = "{safe_msg}"
$balloon.BalloonTipTitle = "{safe_title}"
$balloon.Visible = $true
$balloon.ShowBalloonTip(8000)
Start-Sleep -Seconds 9
$balloon.Dispose()
"""
    subprocess.Popen(
        ["powershell", "-WindowStyle", "Hidden", "-Command", script],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


# Shared queue so the chat router can pick up proactive messages
proactive_queue: list[str] = []
