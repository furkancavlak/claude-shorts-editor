# DESIGN — "Ölmesine 8.65" (bir CS2 yayınından tek an)

## Style Prompt
One continuous piece, not a template. Two persistent windows (streamer cam card, game window)
reshape with eased motion as the story moves: plan -> peek -> death -> reaction -> imitation.
A red countdown pill is the hook object: it states at frame 0 how long until he dies, docks on
the seam, keeps ticking, slows with the slow motion and stamps 0.00 on the death frame.
Type is his own words, locked to the word onsets, left-aligned on one grid (x = 90).

## Colors
- ink #0B0B0D: canvas
- paper #F4F1EA: all type
- kill red #F2322B: the single accent = death / the thing that happens to him (countdown, KAPATIYO, the bar)
- flash white #FFFFFF: only for the "KÖR" flashbang blow-out

## Typography
- Oswald Bold / SemiBold (local TTF, Turkish glyphs verified). Display 110-300 px, tracking 0, line-height 0.9.
- Small labels: Oswald SemiBold 30 px, tracking 0.1em.

## Motion
- Window moves: power3.inOut / expo.inOut 0.6-0.7 s, all windows move together in one gesture.
- Word entrances: mask slide-up 0.45-0.5 s power3/expo.out, <= 0.04 s before the spoken onset.
- Exits are half an entrance, power2.in, upward (or sink with the layer they belong to).
- Impacts only on real events: death frame (shake + red flash), "KÖR" (white blow-out), "LAN" (face punch).

## What NOT to Do
- No text on the face, on the scoreboard, below y 1575 or right of x 930.
- No freeze frame, no label+ring device, no drawn mascots/cursors, no outro, no appended replay.
- No duplicated frames for slow motion (60 fps source, 0.5x minimum).
- No hard cut without a move across it.
