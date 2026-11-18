# tts_tr.ps1 - PLACEHOLDER voice only (real voice = the creator's own recording).
# Speaks a Turkish text file with the Windows built-in "Microsoft Tolga" (tr-TR) voice through
# Windows.Media.SpeechSynthesis (the OneCore/SAPI voice store; System.Speech only sees Zira here).
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File tts_tr.ps1 <text.txt> <out.wav> [rate=1.0]
param([string]$Metin, [string]$Cikti, [double]$Hiz = 1.0)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType = WindowsRuntime]
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Bekle($op, [Type]$t) { $task = $asTask.MakeGenericMethod($t).Invoke($null, @($op)); $task.Wait(-1) | Out-Null; $task.Result }

$s = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$ses = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object { $_.Language -eq 'tr-TR' } | Select-Object -First 1
if (-not $ses) { Write-Output 'HATA: Turkce Windows sesi yok'; exit 2 }
$s.Voice = $ses
try { $s.Options.SpeakingRate = $Hiz } catch { }
$txt = [IO.File]::ReadAllText($Metin, [Text.Encoding]::UTF8)
$akis = Bekle ($s.SynthesizeTextToStreamAsync($txt)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
$okuyucu = New-Object Windows.Storage.Streams.DataReader($akis.GetInputStreamAt(0))
$n = [uint32]$akis.Size
$null = Bekle ($okuyucu.LoadAsync($n)) ([uint32])
$buf = New-Object byte[] $n
$okuyucu.ReadBytes($buf)
[IO.File]::WriteAllBytes($Cikti, $buf)
Write-Output ("TAMAM " + $ses.DisplayName + " " + $n + " bayt")
