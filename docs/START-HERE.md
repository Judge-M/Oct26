# Run Operation Silent Ridge

This is the event operator's starting page. If you have never seen this project
before, follow this page from top to bottom. Do not build images, edit databases,
or invent replacement passwords on event day.

## Six handoff references

| Need | Open this |
|---|---|
| Operator-only setup and recovery commands | [Operator command sheet](event-day-commands.md) |
| Opening projector brief and intro video | [Opening PowerPoint](event-day-deck/opening-brief.pptx) or [LibreOffice ODP](event-day-deck/opening-brief.odp) |
| Closing projector brief, outro and winner reveal | [Closing PowerPoint](event-day-deck/closing-brief.pptx) or [LibreOffice ODP](event-day-deck/closing-brief.odp) |
| Fast help while teams are playing | [Operator runbook](runbook.md) |
| Detailed cold-machine installation | [Event-machine cold start](event-machine-cold-start.md) |
| One-time automatic Windows startup | [Windows boot automation](windows-boot-automation.md) |

The two PowerPoint files are the normal room presentations. The opening video is
slide 4 of the opening deck. The outro is slide 2 of the closing deck, followed
by the winner reveal. Play each video once for the whole room. In LibreOffice,
use the ODP copies instead of opening the PPTX files.

## Before event day

- [ ] Use the published offline release bundle. Do not plan to build from source
      at the venue.
- [ ] Prepare both Windows event servers. The current eleven-team shape uses a
      64 GB / 20-thread primary and an equivalent worker; a single 64 GB host is
      only for a smaller profile.
- [ ] Copy
      `deployment/profiles/example-dynamic-two-host-11-team.json` to the private
      production profile and
      `deployment/examples/two-host-11-team.local.example.json` to the primary
      runtime as `local.json`. Edit the documented event dates, primary/worker
      addresses, asset paths, Docker relay CIDR, and external-certificate paths.
- [ ] Give the primary and worker fixed LAN addresses. The reusable examples
      use `192.168.1.200` and `192.168.1.3` respectively.
- [ ] Make these four names resolve to that address for participant laptops:

  ```text
  ctfd.cyberexperts.org
  iris.cyberexperts.org
  guac.cyberexperts.org
  wazuh.cyberexperts.org
  ```

- [ ] For the normal event configuration, install the valid
      `*.cyberexperts.org` full chain and matching private key on the primary,
      keep `tls.mode` set to `external`, and confirm all four names open on port
      443 from a participant laptop without a certificate warning. The local
      generated-CA/IP-and-port workflow is an explicit fallback, not the normal
      path.
- [ ] Open both room briefs. Test opening slide 4 and closing slide 2 through
      the room speakers, then verify that closing slide 3 is editable.
- [ ] Keep the private runtime folder, TLS private key and backup key off GitHub
      and away from participant handouts.
- [ ] Have an operator install the Windows boot automation on the worker and
      primary, then pass its worker-first reboot test. This is a one-time setup;
      facilitators do not install it or run deployment commands on event day.
- [ ] Treat eleven teams as capacity-valid and representable, not
      performance-certified, until the human/load rehearsal passes on both
      event hosts.

If the server has never been installed, stop here and follow
[Event-machine cold start](event-machine-cold-start.md). Return to this page
when the install receipt exists.

## Thirty minutes before participants arrive

Normal event-day path: power on the **worker first**, then the primary. The
installed scheduled tasks start Docker/SSH, wait for both Docker engines, and
run the safe `up`/`start` flow. A facilitator does not open PowerShell. Wait for
the registration page, test it from a participant laptop, and continue to the
room brief.

That is the entire normal server workflow. Do **not** also run `doctor`, `up`,
`status`, or `start`; the primary boot task replaces those event-day commands.
If the page does not appear, give the primary boot log to the operator and let
the scheduled retry run.

## STOP: operator-only fallback after a boot failure

Everything through the next heading is for the designated operator only, after
boot automation has reported a failure. It is not a facilitator checklist.

Open PowerShell on the primary event server. Set these three paths once. Replace the
examples only if your installation uses different locations:

```powershell
$EventSource = 'C:\Oct26\source'
$EventProfile = 'C:\Oct26\event-profile.json'
$EventRuntime = 'C:\Oct26\event-runtime'
Set-Location $EventSource
```

Set the same private backup key that will be used for restore. It must contain
at least 16 characters. Do not paste this key into chat, documentation or a
screenshot:

```powershell
$env:RIDGE_BACKUP_KEY = 'replace-with-the-private-event-backup-key'
```

Run these commands in order:

```powershell
python -m ridge.deploy doctor --profile $EventProfile --runtime $EventRuntime
python -m ridge.deploy up --profile $EventProfile --runtime $EventRuntime
python -m ridge.deploy status --profile $EventProfile --runtime $EventRuntime
```

Success means `status` reports `event_ready: true`. If `up` says a service is
not ready, run the same `up` command again. It repairs and rechecks the existing
event. It does not reset progress.

Now do three human checks:

- [ ] Open `https://ctfd.cyberexperts.org/silent-ridge/register` on a separate
      participant laptop.
- [ ] Open IRIS, Guacamole and Wazuh from that laptop.
- [ ] Open the PowerPoint and confirm the room audio works.

Registration is protected by the room enrollment code; there is no separate
open/close switch to manage.

## Participant check-in

Boot automation has already started the event. An operator may use this command
only when deliberately resuming a paused event:

```powershell
python -m ridge.deploy start --profile $EventProfile --runtime $EventRuntime
```

Project opening slide 5, which shows:

```text
https://ctfd.cyberexperts.org/silent-ridge/register
Enrollment code: SILENT-RIDGE
```

Each captain registers one team and receives a private retrieval page containing
five CTFd seats, service credentials and three Guacamole desktop names. Tell the
captain to bookmark that private page.

An operator—not the facilitator—can check registrations when diagnosing a
problem:

```powershell
python -m ridge.deploy registration-status --profile $EventProfile --runtime $EventRuntime
```

### One password/link recovery procedure

If a captain loses the private page, do not create another team and do not
invent or reset any passwords:

1. The operator runs the `registration-status` command above and identifies the
   existing team and its registration ID.
2. The operator runs the following command with that ID:

   ```powershell
   python -m ridge.deploy registration-rotate-link --registration-id N --profile $EventProfile --runtime $EventRuntime
   ```

3. Send the newly printed private return URL directly to that captain. The old
   return URL is invalid. The captain downloads the labelled credential handout
   and gives each teammate one of the five individual CTFd seats; the team uses
   the labelled IRIS, Wazuh and Guacamole credentials from that same handout.

Never hand participants `R\secrets\team-credentials.json`; it is operator-only
recovery material.

## Opening the room

1. Put slide 1 of the opening brief on the projector while people settle.
2. Use slides 2 and 3 for the scenario and high-level workflow.
3. Advance to slide 4. The Faye Maxwell opening brief plays automatically.
4. Leave slide 5 projected while captains open the participant landing page.

Participants use IRIS, CTFd and Wazuh in normal laptop browser tabs. They use
Guacamole only for Autopsy, Wireshark, Cutter and the desktop file manager.
They should not browse the web inside a Guacamole desktop.

## While teams are working

Facilitators do not run commands during play. If something fails, give the
operator the symptom and `C:\ProgramData\SilentRidge\logs\primary-boot.log`.
The following controls are for an operator responding to an incident, not part
of the normal room workflow.

An operator can check health with:

```powershell
python -m ridge.deploy status --profile $EventProfile --runtime $EventRuntime
```

Send a message to every team:

```powershell
python -m ridge.cli --state "$EventRuntime\state\state.sqlite" announce --operator EXCON --text "Type the message here"
```

Pause or resume the event clock:

```powershell
python -m ridge.deploy pause --profile $EventProfile --runtime $EventRuntime
python -m ridge.deploy start --profile $EventProfile --runtime $EventRuntime
```

The midpoint operational update and later evidence releases happen
automatically for each team when that team reaches the required progress. An
administrator does not need to release them manually.

For a stuck registration, ticket or desktop, use the matching row in the
[operator runbook](runbook.md). Do not edit the SQLite database or award points
by hand.

## Ending the event

The facilitator's entire closing workflow is in the deck:

1. Let the automatic final assessment publish.
2. Open the closing brief on slide 1, then advance to slide 2. The Faye Maxwell
   closing brief plays automatically for the whole room.
3. Advance to slide 3 and announce the winning team.
4. Conduct the in-person after-action review.

After the room is finished, an **operator—not the facilitator** pauses, creates
a verified backup, and shuts down the stack. These are post-event operator
commands and are not part of participant check-in or facilitation:

```powershell
python -m ridge.deploy pause --profile $EventProfile --runtime $EventRuntime
python -m ridge.deploy backup --profile $EventProfile --runtime $EventRuntime
python -m ridge.deploy down --profile $EventProfile --runtime $EventRuntime
```

`down` keeps event data. Do not add `--volumes` unless the verified backup has
been copied to safe storage and you intentionally want to erase the live event
volumes.

## Three rules that prevent most disasters

1. Re-run `up` when a service is not ready. Do not reset the event.
2. Never open `state.sqlite` with a host database tool while the stack runs.
3. Never run `down --volumes` until a verified backup exists.
