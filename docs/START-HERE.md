# Run Operation Silent Ridge

This is the event operator's starting page. If you have never seen this project
before, follow this page from top to bottom. Do not build images, edit databases,
or invent replacement passwords on event day.

## The five files you need

| Need | Open this |
|---|---|
| Exact setup and start commands | [Event-day command sheet](event-day-commands.md) |
| Projector deck with the intro and outro videos embedded | [Event-day PowerPoint](event-day-deck/event-day-deck.pptx) |
| Slides when PowerPoint is unavailable | [PDF fallback](event-day-deck/event-day-deck.pdf) |
| Fast help while teams are playing | [Operator runbook](runbook.md) |
| Detailed cold-machine installation | [Event-machine cold start](event-machine-cold-start.md) |

The PowerPoint is the normal room presentation. Slide 2 contains the opening
brief and slide 15 contains the closing brief. Both videos play automatically
when their slide appears. Play each video once for the whole room. The PDF does
not contain playable video.

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
- [ ] Open the PowerPoint in the desktop version of Microsoft PowerPoint. Test
      slide 2 and slide 15 through the room speakers.
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

Do not open registration yet.

## Participant check-in

Start the event and open team registration:

```powershell
python -m ridge.deploy start --profile $EventProfile --runtime $EventRuntime
python -m ridge.deploy registration-open --profile $EventProfile --runtime $EventRuntime
Get-Content "$EventRuntime\secrets\registration-enrollment-code"
```

Project this address:

```text
https://ctfd.cyberexperts.org/silent-ridge/register
```

Give the enrollment code only to team captains. Each captain registers one
team and receives a private retrieval page containing five CTFd seats, service
credentials and three Guacamole desktop names. Tell the captain to bookmark
that private page.

Check registrations, then close registration when every team is in:

```powershell
python -m ridge.deploy registration-status --profile $EventProfile --runtime $EventRuntime
python -m ridge.deploy registration-close --profile $EventProfile --runtime $EventRuntime
```

## Opening the room

1. Put slide 1 of the PowerPoint on the projector while people settle.
2. Advance to slide 2. The Faye Maxwell opening brief plays automatically.
3. Continue through slides 3–14 for the participant setup walkthrough.
4. Stop on slide 14. Do not advance to slide 15 until the event is ending.

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
3. Advance the PowerPoint to slide 15. The Faye Maxwell closing brief plays
   automatically for the whole room.
4. Conduct the in-person after-action review.
5. Create a verified backup before shutting anything down.

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
