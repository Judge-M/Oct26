# Conclusion — limited disclosure confirmed

Organizer/producer metadata; narrate only the Script section. Speaker: Faye Maxwell, SOC supervisor for Operation Silent Ridge.

Trigger: Immediately after the participant page publishes **LIMITED DISCLOSURE CONFIRMED — IMMEDIATE CONTAINMENT REQUIRED**. All 20 ticket stages must be complete and the final assessment must be visible. Do not play this cue early.

Performance: Open firmly and identify Faye by name. Deliver the confirmed disclosure and residual CEDAR risk with measured gravity. Slow slightly for the limits and unresolved WS-31 finding. Make the five containment directions crisp and actionable, then close with calm authority rather than celebration.

Estimate: 508 words, 218 seconds at 140 words/minute, before extra pauses. Measure actual recordings. This cue narrates the published final assessment and must not be used as an evidence release.

## Script

All right, everyone. Bring it in.

I'm Faye Maxwell, SOC supervisor for Operation Silent Ridge. I've reviewed the findings your teams submitted, and we now have a defensible picture of what happened.

At zero nine zero six Zulu, workstation WS-17 transmitted a payload matching version three of the Patrol LANTERN movement brief to an external relay at 198.51.100.77. The transfer is tied to request req-72, and the external system acknowledged it.

That is our central finding: a limited disclosure is confirmed.

Version four superseded the transmitted brief at zero nine ten Zulu. It changed the patrol sector from AMBER to BLUE and moved the operational window to ten thirty through eleven thirty Zulu.

That reduced the value of the exposed route information, but it did not eliminate the risk. The check-in word CEDAR remained unchanged between versions. We must therefore treat CEDAR as compromised.

There are important limits to this assessment.

The attempted roster request was denied with an HTTP 403 response and returned zero bytes. We have no evidence that the patrol roster was successfully disclosed.

We also cannot establish who controlled the external relay, whether a person read the transmitted material, or what their intent may have been. The available evidence does not support declaring an enterprise-wide compromise.

Identity records present a separate concern. Session S-41, assigned to the m.ellis account, remained valid after the account password was reset and successfully refreshed at zero nine twenty-six Zulu. A password reset alone did not terminate that session.

We cannot determine from the available records who controlled S-41. That uncertainty does not make the session safe. It must be explicitly revoked.

WS-31 also remains unresolved. Collection from that workstation stopped before we could determine whether the BriefSync task actually executed or was merely present as configuration. We do not have enough evidence to clear the system, and we will not mistake missing telemetry for proof that nothing occurred.

Here is the immediate direction.

First, rotate the CEDAR check-in word and notify Patrol LANTERN through approved operational channels.

Second, revoke session S-41 and review related session activity for additional indicators.

Third, isolate and preserve WS-17. Retain request req-72, the matching payload hash, the corrected timeline, and all associated endpoint and network records.

Fourth, acquire the missing endpoint and network evidence from WS-31. Until that collection is complete, the workstation remains unresolved.

Finally, monitor or block the external relay indicator according to command direction, while preserving visibility for the continuing investigation.

You were asked to separate what the evidence proved from what it merely suggested. You did that.

You confirmed the disclosure without overstating its scope. You identified the information that remained operationally sensitive. You distinguished a denied request from a successful transfer. And you left unresolved systems unresolved when the evidence could not support a stronger conclusion.

Command now has a reliable picture and a clear set of actions.

The final assessment is: limited disclosure confirmed, immediate containment required.

Good work. Preserve your notes and complete your handoffs. The SOC will take it from here.

## Full written echo — operator only

Use the existing database path verified through RUNBOOK.md. Run only after the final assessment is visible, then verify the announcement. Do not run both cues as a batch.

```bash
python -m ridge.cli --state "$RIDGE_STATE" announce --operator EXCON --text 'All right, everyone. Bring it in. I'"'"'m Faye Maxwell, SOC supervisor for Operation Silent Ridge. I'"'"'ve reviewed the findings your teams submitted, and we now have a defensible picture of what happened. At zero nine zero six Zulu, workstation WS-17 transmitted a payload matching version three of the Patrol LANTERN movement brief to an external relay at 198.51.100.77. The transfer is tied to request req-72, and the external system acknowledged it. That is our central finding: a limited disclosure is confirmed. Version four superseded the transmitted brief at zero nine ten Zulu. It changed the patrol sector from AMBER to BLUE and moved the operational window to ten thirty through eleven thirty Zulu. That reduced the value of the exposed route information, but it did not eliminate the risk. The check-in word CEDAR remained unchanged between versions. We must therefore treat CEDAR as compromised. There are important limits to this assessment. The attempted roster request was denied with an HTTP 403 response and returned zero bytes. We have no evidence that the patrol roster was successfully disclosed. We also cannot establish who controlled the external relay, whether a person read the transmitted material, or what their intent may have been. The available evidence does not support declaring an enterprise-wide compromise. Identity records present a separate concern. Session S-41, assigned to the m.ellis account, remained valid after the account password was reset and successfully refreshed at zero nine twenty-six Zulu. A password reset alone did not terminate that session. We cannot determine from the available records who controlled S-41. That uncertainty does not make the session safe. It must be explicitly revoked. WS-31 also remains unresolved. Collection from that workstation stopped before we could determine whether the BriefSync task actually executed or was merely present as configuration. We do not have enough evidence to clear the system, and we will not mistake missing telemetry for proof that nothing occurred. Here is the immediate direction. First, rotate the CEDAR check-in word and notify Patrol LANTERN through approved operational channels. Second, revoke session S-41 and review related session activity for additional indicators. Third, isolate and preserve WS-17. Retain request req-72, the matching payload hash, the corrected timeline, and all associated endpoint and network records. Fourth, acquire the missing endpoint and network evidence from WS-31. Until that collection is complete, the workstation remains unresolved. Finally, monitor or block the external relay indicator according to command direction, while preserving visibility for the continuing investigation. You were asked to separate what the evidence proved from what it merely suggested. You did that. You confirmed the disclosure without overstating its scope. You identified the information that remained operationally sensitive. You distinguished a denied request from a successful transfer. And you left unresolved systems unresolved when the evidence could not support a stronger conclusion. Command now has a reliable picture and a clear set of actions. The final assessment is: limited disclosure confirmed, immediate containment required. Good work. Preserve your notes and complete your handoffs. The SOC will take it from here.'
```
