<!--
Proposed top block for README.md (not applied; README.md itself was not touched).
Paste everything below this comment at the very top of README.md, above "# Short motoru".
Image paths are relative to the repo root, where README.md lives, so the images do not show when this file is previewed from docs/.
-->

<p align="center">
  <img src="docs/gorsel/kapak.png" width="830" alt="Short Motoru (claude-shorts-editor): your raw footage in, a vertical Short out. An editor, not a video generator.">
</p>

**Short Motoru is an editor, not a video generator.** You bring the raw footage (your own game recording, or a stream you are allowed to clip) and tell your own Claude Code agent in the chat what you want. The agent picks the moment and writes the edit as code; ffmpeg, HyperFrames and Whisper render a vertical Short or clip on your own PC.
It needs your own Claude subscription, takes about 25–30 minutes per video, and the edit quality is a first version: the agent looks at frames and measurements, it cannot hear the sound or watch the motion. Tested on one Windows 10 PC.

<p align="center">
  <img src="docs/gorsel/demo.gif" width="720" alt="Left: a 16.5-second horizontal recording with a bar marking the seven parts used; the marker jumps to the source moment each part comes from. Right: the 12.6-second vertical Short cut from it, with the spoken words on screen.">
</p>
<p align="center"><sub>A real job run with this repo on the author's own footage. The bar shows the seven parts of the recording that were used; the Short does not follow the recording's order.</sub></p>

<p align="center">
  <img src="docs/gorsel/nasil-calisir.png" width="830" alt="How it works in three steps: 1. say what you want in the chat, 2. Claude edits in five stages (transcribe, pick the moments, edit as code, technical check, ready), 3. you get the video and one question whose answer goes into your style notebook.">
</p>

A read-only watch page shows the job in progress, the finished videos and the style notebook: what you said you liked, kept in your own words as hints for the next video. The page, the agent's messages and the docs are in Turkish.

<p align="center">
  <img src="docs/gorsel/izleme-sayfasi.png" width="830" alt="The watch page: a clip job at the edit stage (3 of 5), the latest finished Short with the thing the agent tried on purpose, and a style notebook with five entries.">
</p>
<p align="center"><sub>The finished Short is the real job above; the job in progress and the notebook lines are sample data.</sub></p>

**Türkçe belgeler aşağıda.**

---
