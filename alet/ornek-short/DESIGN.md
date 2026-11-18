# short-wow-1 — design

## Style prompt
A GTA VI list Short cut like a motion reel. One motif carries it: Roman-numeral strokes (I, II, III, IV) painted in the Vice City sunset gradient. Each number word drops its numeral onto the frame, the paint opens into a window onto the next shot, and the window grows until it is the frame. Footage is always full-bleed and always moving (eased push-ins, a punch-in on the key word, real-frame speed ramp). Type lives on the shot it belongs to and leaves with it.

## Colors
- Ink `#140A1F` — background, text on slabs
- Paper `#FFF4EA` — spray wash
- Sunset (motif + key-word slab): `#FF3D8B` → `#FF7A3D` → `#FFC23D`
- White `#FFFFFF` — captions, with a dark soft shadow

## Typography
- Anton (local file, Turkish glyphs checked) — every spoken word, uppercase written by hand (İ, I, Ş, Ğ, Ç, Ö, Ü)
- JetBrains Mono (local file) — machine layer: kicker, counter label, source chips

## Motion
- Entrances: expo.out / back.out(1.3–1.6) for strokes, expo.out 0.30 s per word (mask slide up + tracking settle)
- Exits only by the camera (dive, drop, whip) or a mask slide up between phrases
- Every value is a pure function of t (one driver tween)

## What not to do
- No freeze frame + ring, no cards with icons, no pen/chalk drawing, no mascots
- No long quote cards; no slide or web-page look (no rounded UI panels in the middle of the frame)
- No text in the bottom 18 % or near the right edge
- No repeated source seconds between shots; no frame duplication for slow motion
