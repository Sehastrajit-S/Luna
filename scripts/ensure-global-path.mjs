#!/usr/bin/env node
import { execFileSync } from 'node:child_process'
import { platform } from 'node:os'

const isWindows = platform() === 'win32'
const isGlobalInstall =
  process.env.npm_config_global === 'true' ||
  process.env.npm_lifecycle_event === 'global-postinstall'

if (!isWindows || !isGlobalInstall) {
  process.exit(0)
}

function quiet(bin, args) {
  try {
    return execFileSync(bin, args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim()
  } catch {
    return ''
  }
}

const npmBin = process.env.npm_config_prefix || quiet('npm.cmd', ['prefix', '-g'])
if (!npmBin) {
  process.exit(0)
}

const psPath = `'${npmBin.replaceAll("'", "''")}'`
const script = `
$npmBin = ${psPath}
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$parts = @($userPath -split ';' | Where-Object { $_ })
if ($parts -notcontains $npmBin) {
  [Environment]::SetEnvironmentVariable('Path', (($parts + $npmBin) -join ';'), 'User')
  Write-Output "Added $npmBin to user PATH. Open a new terminal to use the luna command."
} else {
  Write-Output "$npmBin is already in user PATH."
}
`

try {
  const out = execFileSync(
    'powershell.exe',
    ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script],
    { encoding: 'utf8' },
  ).trim()
  if (out) console.log(out)
} catch (error) {
  console.warn(`Could not update user PATH automatically: ${error.message}`)
  console.warn(`Add this folder to PATH manually: ${npmBin}`)
}
