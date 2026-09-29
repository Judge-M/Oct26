# Trust the event CA before participant login

The installed event generates a private certificate authority (CA). Its public
certificate is `runtime/wazuh-certs/root-ca.pem`; the private key must never
be placed in a participant pack. The Wazuh Dashboard and participant HTTPS
proxy for IRIS, CTFd and Guacamole use this CA. Stock participant browsers
will not trust it until their own device trusts its public certificate.

## Organizer preparation

1. After final certificate generation, run
   `python scripts/export_participant_ca.py --runtime <runtime-dir> --output <new-participant-pack-dir>`.
   The output contains only the public `root-ca.pem`, an identical certificate
   in Windows-friendly DER form (`root-ca.cer`), and its **certificate DER
   SHA-256** fingerprint. Do not reuse a pack from an earlier runtime; the
   command refuses to replace a different CA in an existing pack.
2. Verify the fingerprint against the installed runtime, and communicate it
   to participants through a separate trusted organizer channel. Distribute
   the public certificate only after that check. If the CA is regenerated, repeat the
   export and client import before reopening the event.
3. Confirm the server certificate includes the actual participant LAN IP or
   DNS name. CA trust cannot repair a hostname mismatch.

## Windows participant device

The repository includes `scripts/setup-participant-windows.ps1` for the final
participant handoff. It accepts a runtime, the private credential handoff path,
and a JSON file containing the four HTTPS URLs. It first checks the public CA,
certificate metadata, and TCP reachability; `-DryRun` and `-VerifyOnly` make no
trust or file changes. A typical verified run is:

```powershell
.\scripts\setup-participant-windows.ps1 `
  -Runtime .\runtime `
  -CredentialFile .\runtime\secrets\team-credentials.json `
  -Config .\participant-endpoints.json -VerifyOnly
```

After independently checking the displayed CA fingerprint, rerun with
`-ImportCertificate`. The script scopes the import to the current user's root
store and asks for confirmation immediately before changing trust. Add
`-OpenTabs` only after the service checks pass; it opens the four HTTPS URLs and
never puts credentials in URLs or browser history. The handoff directory is
ACL-protected and contains only the copied credential file plus a non-secret
README. It is private event state and must not be committed or uploaded.

1. Compare the received `root-ca.cer` fingerprint with the organizer's
   independently supplied fingerprint. The DER file's SHA-256 file hash is
   exactly the certificate fingerprint:

   ```powershell
   (Get-FileHash .\root-ca.cer -Algorithm SHA256).Hash
   ```

   Do not install a CA you cannot verify.
2. On a personally managed Windows device, import the public certificate into
   **Current User → Trusted Root Certification Authorities** using Windows'
   Certificate Import Wizard or, when authorized, PowerShell:

   ```powershell
   Import-Certificate -FilePath .\root-ca.cer -CertStoreLocation Cert:\CurrentUser\Root
   ```

   Complete any Windows trust confirmation that appears. A current-user
   import affects that user; a machine-wide import requires administrator or
   device-management authority. On managed devices, the organization's IT
   team can distribute the CA through Group Policy or its device-management
   system. One observed consent prompt does **not** prove automated managed
   distribution is impossible.
3. Restart the intended participant browser/profile. Open the real HTTPS LAN
   URLs for Wazuh, IRIS, CTFd and Guacamole. Confirm there is no certificate
   interstitial and that login and an authenticated page work for the intended
   participant account. A browser with its own CA store may need its own
   import or enterprise-root setting.

`SSL_CERT_FILE` configures some command-line clients; it does not install a
browser trust root. Do not work around this flow with HTTP, `-k`, or a browser
certificate bypass. Schannel revocation-status behavior (#93) is a separate
client-policy question: record the exact client and policy if it fails after
chain and hostname trust succeed; do not infer all Windows browsers fail from
one `curl` result.

Windows import and managed distribution references:
[Import-Certificate](https://learn.microsoft.com/en-us/powershell/module/pki/import-certificate),
[certificate stores](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/local-machine-and-current-user-certificate-stores), and
[Group Policy distribution](https://learn.microsoft.com/en-us/windows-server/identity/ad-cs/distribute-certificates-group-policy).
