# Motion styles (from awesomeclaude.ai/claude-motion-graphics)

Pick one style per video; every number is a rule, every "no" is a hard constraint.

## The 17 styles

### 1. Swiss International
Off-white #f5f2ea, black #111, one signal red #e63323 used on a single element per shot. One grotesk typeface in two weights. A visible 12-column grid with 4% margins; every element snaps to it. Snaps use cubic-bezier(.7,0,.2,1), lines draw at linear speed. Entrances are wipes and clip reveals, never fades; exits are hard cuts on the beat. No overshoot, no shadows, no gradients.

### 2. Flat vector explainer
Palette #fdf6ec background, #2b2d42 ink, accents #ff6b35, #4ecdc4, #ffd23f. Geometric shapes and simple characters built from circles and rounded rectangles, no gradients. Entrances overshoot with cubic-bezier(0.34,1.56,0.64,1) and settle within 12 frames, groups stagger by 3 frames. Scene changes are carried by a shape that grows to fill the frame and becomes the next background. No crossfades.

### 3. Continuous shape morph
Dark #0d1b2a field, shapes in #f72585, #7209b7, #4cc9f0. No cuts: each idea grows out of the previous shape through a readable in-between form over 18 to 30 frames, then holds for at least 1 second. Liquid moments use metaball blending so drops merge smoothly. Camera stays still; the shapes do the moving.

### 4. Single continuous line drawing
Warm paper #faf7f0, ink #1a1a1a, one accent #c1121f. One line, round caps, constant 4px width, draws itself at a steady linear speed of about 800px/s and never lifts; each picture becomes the next by continuing the line. The camera pans to keep the pen tip in the middle third. One moment where a closed shape floods with the accent colour on a beat.

### 5. Editorial data storytelling
Cream #fffdf7, ink #222, one highlight red #d62828 for the series that matters, muted blue #457b9d for the rest. One reading per screen. Bars and lines grow from the baseline over 20 frames with ease-out, counters roll to the exact value and stop dead. One handwritten-style annotation per chart says why the change matters. Labels at least 28px. Use only numbers from the data provided.

### 6. Isometric miniature world
Orthographic camera at true isometric angles; it slides but never rotates into perspective. Background #eef2f3, ink #2d3142, accent #ef8354, shades #4f5d75 and #bfc0c0. Every block has three flat tones: light top, mid left, dark right. Pieces drop in from 40px above with a small bounce, staggered by 3 frames. To explain a step, lift the roof off a building and show the process inside. Labels use thin leader lines.

### 7. Dark tech keynote
Near-black #0a0a0a stage with a faint hairline grid, white #f5f5f5 type, grey #8b8b8b secondary, one accent #ff5a1f on a single element. Slow long-tail easing cubic-bezier(.16,1,.3,1), 30 to 45 frames per move. Objects are revealed by a soft light sweep rather than fades. One giant number at 30% of frame height counts up to its exact value. No lens flares, no glow, no particles.

### 8. Living screencast
Rebuild the interface in HTML and CSS with its real copy, fonts and colours; no screenshots. A cursor moves on eased curves over 20 to 30 frames, pauses 8 frames, clicks with a small ripple. The camera zooms to 1.6x on each detail that matters, then pulls back. One action every 3 to 4 seconds. Do not show any feature that the product does not have.

### 9. Technical HUD
Dark #050b0f field, cyan #38e8ff primary, amber #ffb000 for warnings, dim #1d3540 grid. All type monospace on a character grid. Numbers scramble through glyphs for 6 to 10 frames then lock to the true value. Target brackets lock in three steps with a tick. Thin 1.5px lines, no bloom, no glitch tearing, every label readable at 1080p.

### 10. Watercolour and ink on paper
Warm paper #f4efe6 with visible grain, ink #2f3e46, washes in #bc4749, #6a994e, #a7c4d2. Paint every element with brush strokes, never plain shapes. Washes spread over 15 to 25 frames and bleed slightly past the ink. Linework wobbles on twos (re-seeded 12 times per second from a fixed seed). No pure white, no pure black, very little text.

### 11. Risograph print
Warm paper #f3ede2. Two spot inks, fluorescent pink #ff48b0 and blue #0078bf (optional yellow #ffe800), overprinted with multiply blending. Each ink plate is misregistered 2 to 4px and stays offset. All tones are halftone dots, never smooth gradients. Animation steps at 12fps while the camera stays smooth.

### 12. Paper cut-out collage
Card colours #e9e3d5, #e76f51, #2a9d8f, #f4a261 with black #1b1b1b details. Every piece has a slightly rough white cut edge and a small hard shadow on the layer below. Characters move in stop-motion steps at 12fps with split-pin joints; the camera drifts smoothly across 3 to 6 parallax layers.

### 13. Hand-drawn cartoon with line boil
Off-white #fffaf0, ink #1c1c1c, flat fills #ff595e, #1982c4, #ffca3a. 24fps animated on twos. Every line has 3 jitter variants cycled so it boils. Fast moves use a smear frame, every big action gets 4 to 6 frames of anticipation, faces act. Variable-width ink lines, no perfect geometric shapes, almost no text.

### 14. 16-bit pixel art
Render to a 320x180 canvas and scale 6x with imageSmoothingEnabled = false. Use one fixed palette (#1a1c2c, #5d275d, #b13e53, #ef7d57, #ffcd75, #a7f070, #38b764, #41a6f6 plus greys). Shading by dithering only. Sprites animate at 8 to 12fps, camera moves in whole pixels, dialogue in a pixel font that types out in a bordered box.

### 15. 1980s VHS tape
Scene in deep #120f1d with neon accents #ff3fa4, #00e5ff and warm #ffd166. Post pass: scanlines, 2 to 3px chroma shift, slight tape noise and an occasional tracking line, all seeded by frame index so the render is deterministic. A chrome title moment. Keep the composition clear underneath; the tape texture never covers key text.

### 16. Toy-like 3D
Three.js, soft studio lighting with one large key and a fill, pastel background #f6e6e4, matte and soft-gloss materials in #ff8fab, #7bdff2, #b2f7ef, #fcbf49. Shallow depth of field on the hero object. Objects land with weight and two small settles, always with a contact shadow. Fixed seeds for any procedural geometry.

### 17. Vertical social captions
1080x1920, all content inside the middle 80% of the frame. Black #000 and white #fff with yellow #ffe600 for the one highlighted word per caption and pink #ff2e63 for emphasis stamps. Captions are 1 to 4 words, chunky with a thick outline, popping in on each beat with a 6 frame scale overshoot. The first second must work with the sound off.

## Notes for this project (Byte / Tech Shorts Autopilot)

- Byte's own look (warm kawaii flat style) sits closest to **#2 Flat vector explainer**; the
  in-video captions should follow **#17 Vertical social captions**. Data-heavy topics can use
  **#5 Editorial data storytelling** for their chart scenes.
- Styles #8 and #16 assume a browser / Three.js renderer; the project renderer is Python +
  SVG + FFmpeg, so treat those two as references unless a browser render step is added.
