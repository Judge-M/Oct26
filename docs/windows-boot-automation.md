# Windows boot automation

This is a **one-time operator installation**, not an event-day procedure. After
it is installed on both Windows event servers, a normal power-on starts Docker
Desktop after the task account signs in. The worker makes Windows OpenSSH and
Docker ready. The primary waits for its local Docker engine and every configured
remote Docker context, then safely resumes the existing event with
`ridge.deploy up` and `ridge.deploy start`.

The automation is deliberately narrow:

- it uses absolute paths from a private host configuration;
- it retries and parses status within a bound and refuses `up` while journal
  state is unknown;
- it computes Task Scheduler's execution limit from the complete configured
  worst-case envelope, plus a safety margin;
- it records UTC logs under `C:\ProgramData\SilentRidge\logs`;
- it is idempotent when reinstalled or triggered more than once;
- it never builds images, changes a profile, resets an event, restores a
  backup, tears down containers, or removes volumes;
- its interactive logon task contains no password. When startup mode is also
  installed, Windows Task Scheduler securely stores the task-account credential
  entered during installation.

## Before installing

1. Finish the normal offline installation and prove the live profile/runtime
   with a manual `up`, `status`, and `start` once.
2. Install Docker Desktop on both servers and enable Linux containers.
3. Install and start Windows OpenSSH on the worker.
4. On the primary, make the configured Docker context reach the worker without
   a prompt. Use SSH-key authentication; do not put an SSH or Windows password
   in either JSON file.
5. Use the same Windows account that owns Docker Desktop and the Docker context
   as the scheduled-task account. It must have **Log on as a batch job** and
   local administrator rights. The installer normally grants the batch-logon
   right through Task Scheduler when it registers the credential.
6. For the current event, begin with
   `deployment/profiles/example-dynamic-two-host-11-team.json` and
   `deployment/examples/two-host-11-team.local.example.json`. Confirm all 33
   slots, the `ridge-worker-02` context, VNC ports 5901–5919, relay ports
   15901–15919, and external wildcard TLS work before installing the tasks.

Docker Desktop is a per-user product. The installer creates a separate logon
task with an actual Task Scheduler `InteractiveToken` principal. Docker Desktop
is guaranteed by this design **after that user signs in**. A password-backed
startup task can additionally try before sign-in, but do not claim unattended
cold-boot operation until that exact machine/account combination passes the
cold-boot acceptance below. Do not change either task to `SYSTEM`: `SYSTEM` has
a different Docker configuration and SSH identity and cannot be assumed to own
the remote context.

## Create the two private configuration files

Copy these examples somewhere outside Git and edit every path for the installed
machines:

- primary: `deployment/windows/primary-boot.example.json`
- worker: `deployment/windows/worker-boot.example.json`

The primary's `source_path`, `profile_path`, `runtime_path`, Python executable,
build-receipt directory, Docker CLI, Docker Desktop executable and Docker config
directory must all be the exact live paths. `remote_docker_contexts` must name
the already tested worker context. The worker needs only its Docker paths,
Docker config directory and log path.

Do not install the example JSON unchanged. On the primary, record the exact
checked-out release path, production profile path, private runtime path, Python
executable, build-receipt directory, Docker configuration directory, and
`ridge-worker-02` context. On the worker, record the Windows account's Docker
configuration directory. These private completed files are the handoff source
of truth; replacement operators must not guess paths from prior chats.

These files contain no password. Keep the primary copy private anyway because
it identifies live server paths.

## Install once on each server

Open **PowerShell as Administrator** from the matching checked-out release.
Install the worker first:

```powershell
Set-Location C:\Oct26\source
.\scripts\windows\Install-SilentRidgeBootTask.ps1 `
  -Role Worker `
  -ConfigPath C:\Oct26\private\worker-boot.json
```

Then install the primary:

```powershell
Set-Location C:\Oct26\source
.\scripts\windows\Install-SilentRidgeBootTask.ps1 `
  -Role Primary `
  -ConfigPath C:\Oct26\private\primary-boot.json
```

Each invocation asks once for the Windows account credential used by that
machine's Docker Desktop. The installer copies only the boot action and the
selected configuration into `C:\ProgramData\SilentRidge\boot`, locks that
directory to the task account, Administrators and SYSTEM, and creates or
replaces two independently-principaled scheduled tasks:

- `Silent Ridge - Worker Boot`
- `Silent Ridge - Worker Logon`
- `Silent Ridge - Primary Boot`
- `Silent Ridge - Primary Logon`

The `Boot` task has only an `AtStartup` trigger and uses the password-backed
principal stored by Task Scheduler. The `Logon` task has only an `AtLogOn`
trigger and uses `InteractiveToken`; it does not store a password. Both actions
are idempotent, and overlapping execution is suppressed.

Re-running the same command is the supported update path after a release or
configuration change. It does not create duplicate tasks.

After installation, save a private operator receipt containing the two config
file paths, scheduled-task names, exact source revision, and date of the last
successful worker-first reboot test. Do not put credentials or private keys in
the receipt.

### Credential-free current-user mode

If the current signed-in Windows account owns Docker Desktop and the Docker
context, install only the real interactive logon task without a credential
prompt:

```powershell
.\scripts\windows\Install-SilentRidgeBootTask.ps1 `
  -Role Worker `
  -ConfigPath C:\Oct26\private\worker-boot.json `
  -CurrentUserInteractive
```

Use the same form with `-Role Primary` on the primary. This mode is idempotent,
updates the matching `Logon` task, and removes a stale password-backed `Boot`
task for that role. It puts no credential in configuration, command arguments,
or task storage. Its tradeoff is explicit: automation begins only after that
user signs in.

Use the default credential-prompt mode when true startup-before-sign-in is
required. Even then, retain the separate interactive logon task as the reliable
Docker Desktop fallback.

## Prove unattended startup before event day

Reboot the **worker first**, then the primary. No facilitator command should be
needed. From an operator account, inspect these read-only locations:

```powershell
Get-ScheduledTask -TaskName 'Silent Ridge - Worker Boot','Silent Ridge - Worker Logon',`
  'Silent Ridge - Primary Boot','Silent Ridge - Primary Logon' |
  Select-Object TaskName, State
Get-Content C:\ProgramData\SilentRidge\logs\worker-boot.log -Tail 40
Get-Content C:\ProgramData\SilentRidge\logs\primary-boot.log -Tail 80
```

After signing in to each task account, success ends with:

```text
worker boot action completed; Docker and SSH are ready
primary boot action completed; event is RUNNING and event_ready
```

Also open the participant registration URL from a separate laptop. Do this
reboot test at least once after any Docker Desktop, Windows account, Docker
context, live profile/runtime, Python path, or release-path change. To certify
startup-before-sign-in, reboot with the password-backed `Boot` task installed,
do not sign in, and verify remotely that the success log and participant URL
appear. If that test has not passed, the supported guarantee is sign-in startup,
not unattended cold boot.

For the normal external-TLS configuration, the acceptance test is not complete
until all four `*.cyberexperts.org` service names resolve locally to the primary
and open on port 443 without a certificate warning.

## Event day

Power on the worker, then the primary. If startup-before-sign-in has not been
cold-boot certified, sign in to the configured account on each machine; the
interactive tasks do the rest. The facilitator does not run PowerShell, Docker,
SSH, or deployment commands. Wait for the registration page, present the opening
PowerPoint, and tell participants to begin.

The boot tasks replace the event-day `doctor`/`up`/`status`/`start` sequence;
do not run those commands in parallel with a healthy boot task.

If the page does not appear, do not reset or reinstall anything. Give the
operator the matching boot log. A failed action leaves the event and its data
in place and Task Scheduler retries it automatically.
