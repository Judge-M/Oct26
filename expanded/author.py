"""Authored coached questions. Generated JSON stays controller-side.

Run from the repository root: python expanded/author.py. The estimates are not
rehearsal results; content targeting missing forensic artifacts is explicitly gated
by the release acceptance record.
"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ridge.scenario import RELEASE_FILES, incident_day
from expanded.native import question_overrides

# title, subject/tool, evidence, selection, dependencies, question/answer pairs.
SPECS = [
('Trace document traffic','Wireshark','network/sensor.pcap','udp.port == 514',[],[
('Which workstation requested plan-v3?','WS-17'),('What request identifier links the plan download?','req-71'),
('What request identifier records the upload?','req-72'),('Which external address appears in the upload record?','198.51.100.77')]),
('Resolve names and compare conversations','Wireshark','network/dns.pcap','dns',[],[
('Which name resolved to the external destination?','relay.archive.example'),('What address did it resolve to?','198.51.100.77'),
('Which client made that lookup?','10.26.10.17'),('What TTL was returned, in seconds?','60')]),
('Reconstruct the viewer download','Autopsy','autopsy/WS17/WS17.aut','browser/downloads.csv',[],[
('At what normalized UTC time was the viewer downloaded?','08:57:00'),('What was the downloaded filename?','brief-viewer.exe'),
('What host served the download URL?','briefs.helpdesk.example'),('What was the recorded target directory?','C:/Downloads')]),
('Investigate persistence','Autopsy','autopsy/WS17/WS17.aut','endpoint/events.csv',[],[
('What task name was registered?','BriefSync'),('Which process registered the task?','brief-viewer.exe'),
('What trigger was recorded?','user logon'),('What is the corrected task registration time?','09:08:00')]),
('Recover and compare cached content','Autopsy','autopsy/WS17/WS17.aut','Deleted Files; inspect the entry ending OVECACH.TXT',[],[
('What patrol name appears in the recovered cache?','LANTERN'),('What version appears in the cached brief?','3'),
('What sector is named?','AMBER'),('What check-in word is present?','CEDAR')]),
('Separate password and session authentication','Wazuh','wazuh/telemetry.jsonl','data.session:S-41',[],[
('Which account was assigned S-41?','m.ellis'),('What external refresh time is recorded?','09:03:00'),
('Which MFA field value appears on that refresh?','previous_claim'),('Did the separate 09:05 password login succeed?','no')]),
('Test the effect of the password reset','Wazuh','wazuh/telemetry.jsonl','data.action:session_refresh',['T06'],[
('When did the password reset occur?','09:20:00'),('What is the late successful session refresh time?','09:26:00'),
('Which session persisted?','S-41'),('Which separate policy action invalidates issued sessions?','session revocation')]),
('Audit document and roster access','Autopsy','autopsy/WS17/WS17.aut','server/access.csv',[],[
('Which object was successfully downloaded in req-71?','plan-v3'),('What status did the roster request return?','403'),
('How many roster body bytes were returned?','0'),('Which request identifies the denied roster access?','req-75')]),
('Compare superseding movement information','Linux file manager','server/version-comparison.csv','Open the CSV in the text viewer',['T08'],[
('When did v4 supersede v3, UTC?','09:10:00'),('What sector does v4 specify?','BLUE'),
('What movement window does v4 specify?','10:30-11:30Z'),('Which check-in word remains unchanged?','CEDAR')]),
('Test a benign comparator','Wazuh','wazuh/telemetry.jsonl','data.host:WS-22',[],[
('Which host has the approved similarly named task?','WS-22'),('Who published its application?','Exercise IT'),
('What is its executable path?','C:/Program Files/Approved/briefsync.exe'),('Which planner account reads v4?','r.chen')]),
('Investigate the unresolved host lead','Wazuh','wazuh/telemetry.jsonl','data.host:WS-31',['T10'],[
('What task name appears on WS-31?','BriefSync'),('At what UTC time was the inventory observed?','08:45:00'),
('When did endpoint collection stop?','08:50:00'),('Does task inventory alone prove execution?','no')]),
('Map collection coverage','Wazuh','wazuh/telemetry.jsonl','data.type:coverage',[],[
('Which workstation has no network collection?','WS-31'),('When does the DOCS-1 collection gap start?','09:14:00'),
('When does that gap end?','09:18:00'),('How many seconds fast is the WS-17 device clock?','120')]),
('Inspect prepared process-log records','Autopsy','autopsy/WS17/WS17.aut','prepared/windows-process.json',[],[
('Which process ID belongs to the viewer?','4240'),('What is its parent executable?','browser.exe'),
('Which workstation generated the record?','WS-17'),('What is the corrected process start time?','08:58:00')]),
('Inspect prepared task-log records','Autopsy','autopsy/WS17/WS17.aut','prepared/windows-task.json',[],[
('What task name was registered?','BriefSync'),('What executable does the task target?','brief-viewer.exe'),
('What device time is shown for registration?','09:10:00'),('Should the already normalized SIEM time be corrected again?','no')]),
('Inspect the prepared memory process tree','Autopsy','autopsy/WS17/WS17.aut','prepared/memory-processes.json',[],[
('What viewer PID is present in the prepared capture?','4240'),('What parent PID is recorded?','3100'),
('What executable belongs to the parent?','browser.exe'),('What path is supplied to the viewer as its cache argument?','C:/Temp/move-cache.txt')]),
('Correlate prepared memory connections','Autopsy','autopsy/WS17/WS17.aut','prepared/memory-connections.json',[],[
('Which PID owns the external connection?','4240'),('What remote address is recorded?','198.51.100.77'),
('What remote port is recorded?','443'),('Does a connection entry prove a human read the payload?','no')]),
('Inspect the harmless training binary configuration','Cutter','binary/brief-viewer-training','Windows > Strings',[],[
('What destination is embedded as configuration?','198.51.100.77'),('What path is embedded as configuration?','/upload'),
('What task label appears as a string?','BriefSync'),('Does this training binary perform network calls?','no')]),
('Follow a small static code example','Cutter','binary/brief-viewer-training','Functions > classify_version',[],[
('Which integer marks the cached version?','3'),('What text is returned when the input is 3?','cached v3'),
('What text is returned for other inputs?','other version'),('Does a code branch prove the incident executed it?','no')]),
('Verify the transmitted payload','Linux file manager','network/dlp-metadata.json','Open metadata and compare its sha256 with server/catalog.csv',['T01','T05'],[
('Which request is tied to the DLP body?','req-72'),('What brief version matches that body?','3'),
('What upload time is recorded, UTC?','09:06:00'),('Does the HTTP acknowledgment prove human reading?','no')]),
('Test the limits of the overall exposure conclusion','Wazuh','wazuh/telemetry.jsonl','data.request:req-72',['T07','T09','T11','T19'],[
('Which brief version is supported by the payload match?','3'),('Is successful roster disclosure established by the denied request?','no'),
('Can WS-31 be cleared with the available telemetry?','no'),('Does the evidence establish adversary intent?','no')])
]

LIMITS = {
 'Wireshark':'Replayed or reconstructed evidence; transmission metadata does not establish human receipt, reading, or intent.',
 'Autopsy':'Prepared evidence is limited to the specified collection. Presence of an artifact is not proof of every related action.',
 'Wazuh':'Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.',
 'Cutter':'This harmless training surrogate demonstrates static inspection, not behavior of an acquired incident executable.',
 'Linux file manager':'The supplied document or export supports only the stated comparison, not human receipt or adversary intent.'}

FINDINGS = [
['WS-17 is the workstation associated with the plan-v3 request.', 'The plan download is correlated by request identifier req-71.', 'Request req-72 identifies the outbound upload.', 'The upload record identifies 198.51.100.77 as its external destination.'],
['The DNS record maps relay.archive.example to an address.', 'The DNS answer is 198.51.100.77.', 'The recorded DNS client is WS-17 at 10.26.10.17.', 'The DNS response records a 60-second TTL.'],
['The browser export records the viewer download at 08:57:00 UTC.', 'The recorded download filename is brief-viewer.exe.', 'The download URL names briefs.helpdesk.example; this does not establish the original delivery mechanism.', 'The browser target path places the download in C:/Downloads.'],
['The registered task is named BriefSync.', 'The task-registration record names brief-viewer.exe as the registering process.', 'The recorded task trigger is user logon.', 'After subtracting the documented 120-second device offset, task registration occurred at 09:08:00 UTC.'],
['The recovered cache names fictional patrol LANTERN.', 'The recovered cache contains movement brief version 3.', 'The cached version names sector AMBER.', 'The cached version includes check-in word CEDAR.'],
['The identity record assigns session S-41 to m.ellis.', 'The external S-41 refresh is timestamped 09:03:00 UTC.', 'The refresh carries previous_claim, rather than a newly challenged MFA result.', 'The separate password-login attempt at 09:05 failed; it must not be conflated with session refresh success.'],
['The password-reset record is timestamped 09:20:00 UTC.', 'A later session refresh succeeded at 09:26:00 UTC.', 'The later successful refresh reused S-41.', 'The supplied identity policy treats explicit session revocation separately from a password reset. No containment change was performed by participants.'],
['Request req-71 returned plan-v3.', 'The roster request returned HTTP 403.', 'The denied roster request returned zero body bytes.', 'Request req-75 identifies the denied roster access, not a successful disclosure.'],
['The supplied version history records v4 superseding v3 at 09:10:00 UTC.', 'Version 4 specifies sector BLUE.', 'Version 4 specifies the 10:30–11:30Z movement window.', 'CEDAR is unchanged between the supplied v3 and v4 records.'],
['WS-22 has a similarly named approved task; its name alone is not a compromise indicator.', 'The WS-22 inventory identifies Exercise IT as publisher.', 'The approved WS-22 application path is C:/Program Files/Approved/briefsync.exe.', 'The server audit records r.chen as the planner reading v4.'],
['WS-31 inventory contains a task named BriefSync, creating an unresolved scope lead.', 'The WS-31 inventory observation is timestamped 08:45:00 UTC.', 'WS-31 endpoint collection stopped at 08:50:00 UTC.', 'Task inventory alone does not establish execution on WS-31. Further collection would be required.'],
['The coverage record lists no network collection for WS-31.', 'DOCS-1 audit collection has a gap beginning at 09:14:00 UTC.', 'DOCS-1 audit collection resumes at 09:18:00 UTC.', 'The documented WS-17 device offset is 120 seconds fast; normalized records must not receive a second correction.'],
['The prepared process record assigns PID 4240 to the viewer.', 'The prepared process record names browser.exe as parent.', 'The prepared process record is attributed to WS-17.', 'The process start maps to 08:58:00 UTC after the documented device correction.'],
['The prepared task record names BriefSync.', 'The task target is brief-viewer.exe.', 'The task-registration device timestamp is 09:10:00.', 'SIEM timestamps are already normalized and must not be corrected again.'],
['The prepared process view includes viewer PID 4240.', 'The viewer process has recorded parent PID 3100.', 'The parent record identifies browser.exe.', 'The prepared command line includes cache path C:/Temp/move-cache.txt.'],
['The prepared connection view associates the external connection with PID 4240.', 'The prepared connection has remote address 198.51.100.77.', 'The prepared connection has remote port 443.', 'A connection entry cannot establish human receipt or reading of the payload.'],
['The training surrogate contains destination string 198.51.100.77.', 'The training surrogate contains configuration path /upload.', 'The training surrogate contains task-label string BriefSync.', 'The supplied training surrogate performs no network calls; its strings are for static inspection.'],
['The classify_version example compares its input with integer 3.', 'The input-3 branch returns the text cached v3.', 'The other branch returns the text other version.', 'The existence of a static branch does not establish that it executed during the incident.'],
['The DLP metadata links the supplied body to req-72.', 'The body hash comparison matches movement brief v3.', 'The DLP upload timestamp is 09:06:00 UTC.', 'An HTTP acknowledgment does not prove a human read the transmitted body.'],
['The matched payload supports transmission of movement brief v3.', 'The denied roster request does not establish successful roster disclosure.', 'The available inventory and collection gaps cannot clear WS-31.', 'The supplied evidence does not establish adversary intent.']
]


def build(config=None):
    config = config or json.loads(Path(__file__).with_name('config.json').read_text(encoding='utf-8'))
    day = incident_day(config['exercise_date'])
    tickets=[]
    native = question_overrides()
    for n,(title,tool,evidence,selection,requires,pairs) in enumerate(SPECS,1):
        findings = FINDINGS[n-1]
        limitation = LIMITS[tool]
        if n in native:
            title, selection, pairs, findings = native[n]
            limitation = ('Isolated native training reconstruction with actual acquisition UTC. '
                          'It does not replace the historical incident timeline. Consult the record provenance and original hash.')
        tid=f'T{n:02}'
        if tool=='Autopsy':
            opening=['Copy the prepared case template to ~/Cases/WS17; keep /evidence mounted read-only.',
                'Open Autopsy > Open Existing Case > ~/Cases/WS17/WS17.aut.',
                'In Data Sources, expand the prepared evidence source and locate '+selection+'.',
                'Select the record; use the Text tab and its source reference. Compare the cited original artifact.']
        elif tool=='Wazuh':
            opening=['Open the Wazuh shortcut and sign in with the supplied read-only account.',
                'Open Discover and choose the silent-ridge-* data view.',
                f'Set an absolute UTC range of {day} 08:00:00 through 09:30:00.',
                'Search '+selection+'. Expand a row to inspect fields; compare adjacent records and policy.']
            if selection=='data.type:coverage':
                opening[2]='Use a data view without a time field for coverage records: these describe collection intervals, not individual event timestamps.'
        elif tool=='Wireshark':
            opening=['Open Wireshark > File > Open > /evidence/'+evidence+'.',
                'Select View > Time Display Format > UTC Date and Time of Day.',
                'Enter '+selection+' in the display filter and press Enter.',
                'Select a packet and expand its protocol fields. For syslog, inspect the embedded proxy record; the outer collector addresses are not incident endpoints.']
        elif tool=='Cutter':
            opening=['Open Cutter > Open > /evidence/'+evidence+'. Use normal analysis; do not run or debug it.',
                'Open '+selection+'.', 'Select the relevant string or function. Inspect references and the graph/disassembly.',
                'Compare configuration with runtime evidence; distinguish possible behavior from observed behavior.']
        else:
            opening=['Open Evidence on the desktop, then '+evidence+'.',selection+'.',
                'Compare named fields and preserve the distinction between metadata and document contents.']
        questions=[]
        for i,(prompt,answer) in enumerate(pairs,1):
            qid=f'{tid}-Q{i}'
            questions.append(dict(id=qid,prompt=prompt,answer=answer,tool=tool,evidence='/evidence/'+evidence,
                purpose='Use '+title.lower()+' to answer this specific question and identify the limits of the evidence.',
                steps=opening,format='Enter only the requested value; times use HH:MM:SS UTC. Case and outer whitespace are ignored.',
                recovery='If no results appear, clear filters, check the evidence release and absolute UTC range, and reopen your writable case. Never re-ingest a large image during the activity.',
                hints=['Start with '+selection+' and read the fields named in the question.',
                       'Compare the selected record with adjacent events; apply clock correction only to device_time.',
                       'Walkthrough: '+prompt+' The supplied record/comparison yields '+answer+'. Enter '+answer+'. '+limitation],
                finding=dict(text=findings[i-1],evidence=[evidence+' ('+selection+')'],limitation=limitation)))
        tickets.append(dict(id=tid,title=title,subject=tool,requires=requires,release_files=RELEASE_FILES.get(tid, []),estimate_minutes=65,
            estimate_basis='Unmeasured planning allowance: opening/orientation 10, four guided investigations 40, cross-check and recovery 15. Must be replaced by beginner rehearsal measurements.',questions=questions))
    return tickets


if __name__=='__main__':
    Path(__file__).with_name('tickets.json').write_text(json.dumps(build(),indent=2)+'\n',encoding='utf-8')
