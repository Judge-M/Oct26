# Public HTTPS certificates for an offline LAN event

The event can use a publicly trusted certificate while remaining fully local.
The deployment already has one Nginx edge proxy for IRIS, CTFd and Guacamole;
this mode configures that proxy with organizer-supplied certificate files. It
does not replace the proxy with a second Caddy stack.

## What the organizer needs to do

1. Use a domain you control, for example `cyberexperts.org`.
2. Choose four service names, for example:

   - `iris.cyberexperts.org`
   - `ctfd.cyberexperts.org`
   - `guac.cyberexperts.org`
   - `wazuh.cyberexperts.org`

3. Obtain one certificate whose SANs cover all four names. A wildcard such as
   `*.cyberexperts.org` also covers them. DNS-01 is the preferred ACME method
   because the event server does not need to be reachable from the Internet.
   Run issuance and renewal while Internet access and the DNS provider API are
   available, before event day.
4. Keep the private key on the event host only. Do not commit it, put it in a
   participant pack, or paste it into chat.

The repository does not need DNS-provider credentials. If using an ACME client,
configure its provider plugin on the preparation machine, issue the certificate,
and transfer only the resulting full-chain certificate and private key to the
event host through your normal secure channel.

## Local DNS without router changes

On event day the names must resolve to the event server's LAN address, for
example `192.168.1.200`. Public DNS cannot reliably provide this while the
venue is offline, and a public record pointing at an RFC1918 address is not a
substitute for local name resolution. Use one of these organizer-controlled
options:

- distribute a hosts-file entry for each name to participant devices; or
- run a small local DNS service and have the event onboarding instructions set
  that resolver on participant devices.

No router port forwarding is required. The certificate is valid because the
browser connects to the DNS name, while local DNS sends that name to the LAN
server.

## Runtime configuration

Keep the certificate paths outside the repository and add this host-local block
to `R/local.json`:

```json
"tls": {
  "mode": "external",
  "certificate": "C:/event-secrets/cyberexperts-fullchain.pem",
  "key": "C:/event-secrets/cyberexperts-privkey.pem",
  "hostnames": {
    "iris": "iris.cyberexperts.org",
    "ctfd": "ctfd.cyberexperts.org",
    "guac": "guac.cyberexperts.org",
    "wazuh": "wazuh.cyberexperts.org"
  }
}
```

The deployment validates that the certificate covers every configured hostname
and that the private key matches it. It copies the public edge pair into the
private runtime only; Wazuh's internal indexer/manager trust graph continues to
use the generated event CA. The external mode also disables the participant
certificate-pack/CRL requirement, because the public CA chain is trusted by
stock browsers.

All four public service URLs use the shared HTTPS listener on port 443:
`https://ctfd.cyberexperts.org`, `https://iris.cyberexperts.org`,
`https://guac.cyberexperts.org`, and `https://wazuh.cyberexperts.org`. The
application container ports remain internal implementation details. The HTTP
CRL listener on port 8080 is retained only for the generated-CA fallback.

## Renewal and fallback

Renew certificates while online, then replace the host-local files and restart
the stack during a maintenance window. A pre-issued certificate remains valid
when the venue Internet connection drops; ACME renewal does not work while
air-gapped. If the public certificate expires, switch back to the default
`"mode": "generated"` and follow `docs/participant-ca-trust.md` to distribute
the event CA before reopening the event.

Do not use `.local` as the primary public-certificate name and do not ask
participants to click through browser certificate warnings.
