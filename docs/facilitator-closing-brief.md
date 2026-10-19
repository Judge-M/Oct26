# Facilitator closing brief

Use this brief only after a team completes T20. The platform reveals the same
assessment automatically in CTFd and IRIS; this script gives the facilitator or
the closing audiovisual the spoken version of that canonical record.

## On-screen title

**LIMITED DISCLOSURE CONFIRMED — IMMEDIATE CONTAINMENT REQUIRED**

## Spoken brief

At 09:06 UTC, WS-17 transmitted a payload matching Patrol LANTERN movement
brief version 3 to the external relay at `198.51.100.77` through request
`req-72`. Four minutes later, version 4 superseded that brief. The sector moved
from AMBER to BLUE and the movement window became 10:30–11:30Z, but the
check-in word CEDAR did not change. The older brief therefore still exposed an
active operational element.

The roster request did not succeed: it returned HTTP 403 and zero body bytes.
Session S-41, assigned to `m.ellis`, survived the password reset and refreshed
at 09:26 UTC. The evidence does not establish who controlled that session,
whether a human read the transmitted payload, or adversary intent. WS-31 also
cannot be cleared because collection stopped before execution could be
determined.

The final assessment is a confirmed, limited disclosure from WS-17 with
residual operational risk. It is not evidence of roster theft, enterprise-wide
compromise, or actor attribution.

The required response is to rotate CEDAR, explicitly revoke S-41, isolate and
preserve WS-17, collect the missing evidence from WS-31, and monitor or block
the external relay indicator.

## Facilitator discussion prompts

1. Why is transmission enough to declare a disclosure even though human
   reading is not established?
2. Why does v4 reduce some risk without eliminating the exposure?
3. Why is password reset insufficient containment for S-41?
4. Which statements are confirmed, and which remain unresolved?
5. What additional evidence would be required to attribute intent or clear
   WS-31?

## Audiovisual integration

When the closing media is ready, set `RIDGE_FINAL_BRIEF_URL` in the event
environment before starting the central stack. Completed teams will receive a
**Play the unlocked closing audiovisual brief** link. If it is unset, the
participant page tells the team that the facilitator can present the closing
brief in person.

Do not place the media URL or the conclusion on a pre-completion participant
page. The server adds the conclusion to the rendered context only after all 20
ticket stages are complete.
