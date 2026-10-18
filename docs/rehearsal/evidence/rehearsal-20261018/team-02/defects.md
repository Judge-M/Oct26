# Team 2 rehearsal defects and blockers

## Blocking defects

1. **CTFd event route fails.** The trusted route `:8083/silent-ridge` showed a visible HTTP 500 page, “An Internal Server Error has occurred.” A retry did not produce the question form and later hung. This prevented all eight submissions and every Correct-result verification.
2. **Wazuh authentication unavailable for this rehearsal.** The trusted `:8443/app/login` surface remained at the login screen and showed “Invalid username or password. Please try again.” No current Wazuh reader credential was available in the user-provided role credentials, so the telemetry file could not be inspected.
3. **IRIS account naming inconsistency.** The supplied Team 2 login identifier was rejected by IRIS with “Wrong credentials.” A previously observed Team 2 participant login did authenticate and showed the event queue as Team 2. This should be reconciled in the fresh-event credential sheet.

## Non-blocking defects

4. **IRIS internal links expose the raw IP.** The visible “Questions and help,” “Scoreboard,” “Start this ticket's questions,” and shared-task links used `192.168.1.200` rather than the trusted Tailscale hostname. The rehearsal did not follow those links.
5. **Remote desktop Wireshark filter input is unreliable.** The filter bar accepted only a partial character during attempts to enter the coached `dns` filter and displayed a filter error. The unfiltered `dns.pcap` packet list remained visible and was used for the human evidence inspection.
6. **Initial Wireshark direct-open attempt reported file not found.** Opening `dns.pcap` through the GTK file chooser produced a visible file-not-found error after the typed path was malformed. The same file opened successfully from the mounted Evidence directory.

## Scope status

- T02: held by Team 2; evidence route inspected; 0 questions verified Correct.
- T12: not claimed; no other ticket claimed.
- No admin checks were performed because the participant workflow was blocked and no separate facilitator/admin credentials or surface were provided in the resumed instruction.

