# Run Operation Silent Ridge

This is the event operator's starting page. If you have never seen this project
before, follow this page from top to bottom. Do not build images, edit databases,
or invent replacement passwords on event day.

## The five files you need

| Need | Open this |
|---|---|
| Exact setup and start commands | [Event-day command sheet](event-day-commands.md) |
| Opening projector brief and intro video | [Opening PowerPoint](event-day-deck/opening-brief.pptx) or [LibreOffice ODP](event-day-deck/opening-brief.odp) |
| Closing projector brief, outro and winner reveal | [Closing PowerPoint](event-day-deck/closing-brief.pptx) or [LibreOffice ODP](event-day-deck/closing-brief.odp) |
| Fast help while teams are playing | [Operator runbook](runbook.md) |
| Detailed cold-machine installation | [Event-machine cold start](event-machine-cold-start.md) |

The two PowerPoint files are the normal room presentations. The opening video is
slide 4 of the opening deck. The outro is slide 2 of the closing deck, followed
by the winner reveal. Play each video once for the whole room. In LibreOffice,
use the ODP copies instead of opening the PPTX files.

## Before event day

- [ ] Use the published offline release bundle. Do not plan to build from source
      at the venue.
- [ ] Confirm Docker is installed and running on the event server.
- [ ] Confirm the event server has at least 32 GB RAM, 16 CPU cores and 100 GB
      free SSD space. The current 64 GB server is suitable.
- [ ] Give the event server a fixed LAN address.
- [ ] Make these four names resolve to that address for participant laptops:

  ```text
  ctfd.cyberexperts.org
  iris.cyberexperts.org
  guac.cyberexperts.org
  wazuh.cyberexperts.org
  ```

- [ ] From a participant laptop, open all four names without a certificate
      warning.
- [ ] Open both room briefs. Test opening slide 4 and closing slide 2 through
      the room speakers, then verify that closing slide 3 is editable.
- [ ] Keep the private runtime folder, TLS private key and backup key off GitHub
      and away from participant handouts.

If the server has never been installed, stop here and follow
[Event-machine cold start](event-machine-cold-start.md). Return to this page
when the install receipt exists.

## Thirty minutes before participants arrive

Open PowerShell on the event server. Set these three paths once. Replace the
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

Start the event:

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

Check registrations at any time:

```powershell
python -m ridge.deploy registration-status --profile $EventProfile --runtime $EventRuntime
```

## Opening the room

1. Put slide 1 of the opening brief on the projector while people settle.
2. Use slides 2 and 3 for the scenario and high-level workflow.
3. Advance to slide 4. The Faye Maxwell opening brief plays automatically.
4. Leave slide 5 projected while captains open the participant landing page.

Participants use IRIS, CTFd and Wazuh in normal laptop browser tabs. They use
Guacamole only for Autopsy, Wireshark, Cutter and the desktop file manager.
They should not browse the web inside a Guacamole desktop.

## While teams are working

Check health at any time:

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

1. Pause the clock.
2. Let the automatic final assessment publish.
3. Open the closing brief on slide 1, then advance to slide 2. The Faye Maxwell
   closing brief plays automatically for the whole room.
4. Advance to slide 3 and announce the winning team.
5. Conduct the in-person after-action review.
6. Create a verified backup before shutting anything down.

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
