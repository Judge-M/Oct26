[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$adminUrls = @(
    'https://ctfd.cyberexperts.org/login?next=/admin'
    'https://iris.cyberexperts.org/login'
    'https://guac.cyberexperts.org/guacamole/'
    'https://wazuh.cyberexperts.org/'
)

foreach ($url in $adminUrls) {
    Start-Process $url
    Start-Sleep -Milliseconds 200
}
