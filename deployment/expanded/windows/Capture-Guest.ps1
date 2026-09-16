$ErrorActionPreference = 'Stop'
try {
    if ((Get-CimInstance Win32_ComputerSystem).Model -ne 'Virtual Machine' -or [Security.Principal.WindowsIdentity]::GetCurrent().Name -notlike '*\WDAGUtilityAccount') { throw 'Sandbox guest required' }
    if (Test-Path C:\Fixture\capture-started.json) { throw 'Use a fresh Sandbox for another capture' }
    New-Item -ItemType Directory -Force C:\Fixture,C:\Temp | Out-Null
    @{started=(Get-Date).ToUniversalTime().ToString('o');computer=$env:COMPUTERNAME;scenario_host='WS-17';provenance='Isolated training reconstruction, not original incident acquisition'} | ConvertTo-Json | Set-Content C:\Fixture\capture-started.json
    Copy-Item C:\Fixture\capture-started.json C:\CaptureOutput\capture-started.json
    & auditpol /set /subcategory:'Process Creation' /success:enable *> C:\CaptureOutput\audit-process.txt
    if ($LASTEXITCODE -ne 0) { throw 'Cannot enable process auditing' }
    & auditpol /set /subcategory:'Other Object Access Events' /success:enable *> C:\CaptureOutput\audit-task.txt
    if ($LASTEXITCODE -ne 0) { throw 'Cannot enable task auditing' }
    & wevtutil sl Microsoft-Windows-TaskScheduler/Operational /e:true
    if ($LASTEXITCODE -ne 0) { throw 'Cannot enable task log' }
    $loopback = Get-NetIPAddress -AddressFamily IPv4 | Where-Object IPAddress -eq '127.0.0.1' | Select-Object -First 1
    if (!$loopback) { throw 'Guest loopback interface was not found' }
    New-NetIPAddress -InterfaceIndex $loopback.InterfaceIndex -IPAddress 198.51.100.77 -PrefixLength 32 -AddressFamily IPv4 | Out-Null
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Parse('198.51.100.77'),443)
    $listener.Start()
    'TRAINING ONLY: plan-v3 movement cache; req-71; req-72; no real documents or credentials.' | Set-Content C:\Temp\move-cache.txt
    $viewer = @'
using System;
using System.Diagnostics;
using System.IO;
using System.Net.Sockets;
using System.Threading;
public class Viewer {
  public static void Main(string[] args) {
    if (Array.IndexOf(args,"--task") >= 0) { Console.WriteLine("Training scheduled action"); return; }
    byte[] cache = File.ReadAllBytes(@"C:\Temp\move-cache.txt");
    TcpClient client = new TcpClient("198.51.100.77",443);
    File.WriteAllText(@"C:\Fixture\viewer-ready.txt",Process.GetCurrentProcess().Id.ToString());
    while (!File.Exists(@"C:\Fixture\register-task.flag")) Thread.Sleep(100);
    dynamic scheduler = Activator.CreateInstance(Type.GetTypeFromProgID("Schedule.Service"));
    scheduler.Connect();
    dynamic folder = scheduler.GetFolder(@"\");
    string xml = "<Task version=\"1.2\" xmlns=\"http://schemas.microsoft.com/windows/2004/02/mit/task\"><RegistrationInfo><Description>Harmless Silent Ridge training fixture</Description></RegistrationInfo><Triggers><LogonTrigger><Enabled>true</Enabled></LogonTrigger></Triggers><Settings><Enabled>true</Enabled><ExecutionTimeLimit>PT1M</ExecutionTimeLimit></Settings><Actions><Exec><Command>C:\\Fixture\\brief-viewer.exe</Command><Arguments>--task</Arguments></Exec></Actions></Task>";
    folder.RegisterTask("BriefSync",xml,6,null,null,3,null);
    File.WriteAllText(@"C:\Fixture\task-ready.txt",DateTime.UtcNow.ToString("o"));
    while (!File.Exists(@"C:\Fixture\stop.flag")) { GC.KeepAlive(cache); GC.KeepAlive(client); Thread.Sleep(1000); }
    client.Close();
  }
}
'@
    Add-Type -TypeDefinition $viewer -Language CSharp -ReferencedAssemblies System.dll,System.Core.dll,Microsoft.CSharp.dll -OutputAssembly C:\Fixture\brief-viewer.exe -OutputType ConsoleApplication
    $browser = @'
using System;
using System.Diagnostics;
using System.Threading;
public class Browser {
  public static void Main() {
    Process viewer = Process.Start(new ProcessStartInfo(@"C:\Fixture\brief-viewer.exe","--cache C:/Temp/move-cache.txt") { UseShellExecute=false });
    viewer.WaitForExit();
  }
}
'@
    Add-Type -TypeDefinition $browser -Language CSharp -OutputAssembly C:\Fixture\browser.exe -OutputType ConsoleApplication
    $parent = Start-Process C:\Fixture\browser.exe -PassThru -WindowStyle Hidden
    for ($attempt=0; $attempt -lt 100 -and !(Test-Path C:\Fixture\viewer-ready.txt); $attempt++) { Start-Sleep -Milliseconds 100 }
    if (!(Test-Path C:\Fixture\viewer-ready.txt)) { throw 'Viewer did not establish the training connection' }
    $connection = $listener.AcceptTcpClient()
    New-Item -ItemType File C:\Fixture\register-task.flag | Out-Null
    for ($attempt=0; $attempt -lt 100 -and !(Test-Path C:\Fixture\task-ready.txt); $attempt++) { Start-Sleep -Milliseconds 100 }
    if (!(Test-Path C:\Fixture\task-ready.txt)) { throw 'Viewer did not register the training task' }
    $viewerId = [int](Get-Content C:\Fixture\viewer-ready.txt)
    Get-CimInstance Win32_Process | Where-Object ProcessId -in @($viewerId,$parent.Id) | Select-Object ProcessId,ParentProcessId,Name,CommandLine,CreationDate | ConvertTo-Json -Depth 4 | Set-Content C:\CaptureOutput\observed-processes.json
    Get-NetTCPConnection -OwningProcess $viewerId | Select-Object OwningProcess,LocalAddress,LocalPort,RemoteAddress,RemotePort,State | ConvertTo-Json | Set-Content C:\CaptureOutput\observed-connections.json
    Export-ScheduledTask -TaskName BriefSync | Set-Content C:\CaptureOutput\BriefSync.xml
    Start-Sleep -Seconds 2
    & wevtutil epl Security C:\CaptureOutput\Security.evtx /ow:true
    if ($LASTEXITCODE -ne 0) { throw 'Security export failed' }
    & wevtutil epl Microsoft-Windows-TaskScheduler/Operational C:\CaptureOutput\TaskScheduler.evtx /ow:true
    if ($LASTEXITCODE -ne 0) { throw 'Task export failed' }
    @{
        scenario_host='WS-17';capture_host=$env:COMPUTERNAME;viewer_pid=$viewerId;parent_pid=$parent.Id
        capture_time_utc=(Get-Date).ToUniversalTime().ToString('o');clock_semantics='Actual acquisition UTC; no historic clock shift applied'
        network='Networking disabled; 198.51.100.77/32 assigned to guest loopback; TCP 443 is a local harmless listener, not Internet traffic'
        executable='Harmless C# training surrogate compiled in the guest; browser.exe is a parent surrogate, not a real browser'
        windows=(Get-CimInstance Win32_OperatingSystem).Version
    } | ConvertTo-Json | Set-Content C:\CaptureOutput\native-provenance.json
    Copy-Item C:\Fixture\brief-viewer.exe,C:\Fixture\browser.exe,C:\Temp\move-cache.txt C:\CaptureOutput
    $ErrorActionPreference = 'Continue'
    & C:\CaptureInput\winpmem.exe acquire C:\CaptureOutput\WS17.raw *> C:\CaptureOutput\acquisition.log
    $captureExit = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    if ($captureExit -ne 0) { throw "WinPmem acquisition failed: $captureExit" }
    Get-FileHash C:\CaptureOutput\WS17.raw -Algorithm SHA256 | Select-Object Algorithm,Hash | ConvertTo-Json | Set-Content C:\CaptureOutput\memory-sha256.json
    'complete' | Set-Content C:\CaptureOutput\capture-status.txt
    New-Item -ItemType File C:\Fixture\stop.flag | Out-Null
    $connection.Close()
    $listener.Stop()
} catch {
    $_ | Out-String | Set-Content C:\CaptureOutput\capture-error.txt
    'failed' | Set-Content C:\CaptureOutput\capture-status.txt
    exit 1
}
