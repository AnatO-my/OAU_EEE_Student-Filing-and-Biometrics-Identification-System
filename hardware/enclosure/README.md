# Desk fingerprint terminal enclosure - revision B

This is a new parametric engineering draft inspired by the supplied multi-view screenshots of
[Fingerprint by brixdeguzman9 on Sketchfab](https://sketchfab.com/3d-models/fingerprint-cc1cd05745644330aa10525a5c7c104c).
The public model is not downloadable. Its preview establishes appearance, not
physical dimensions. The reference image is retained for design comparison only;
no reuse license was supplied in its public metadata.

Overall size is approximately **193 W x 102 D x 100 H mm**, including the front
trim. Main housing (with rear cover) is 150 W x 100 D x 100 H. The separate
battery pod is 40 wide, plus a 3-mm outer cover. The front is vertical and flat,
parallel to the rear. Walls are nominally 3.2 mm. The removable rear cover and
pod cover are 3 mm. This revision replaces the sloped revision A.

The left front control panel is 80 x 84 x 1.2, with rounded R6 corners and three
buttons. The right sensor panel is 44 x 80 x 2, also R6. The battery cover has
a recessed 79.6 x 79.6 x 0.8 grey cosmetic insert. Left-side vent slots follow
the reference's appearance. The main front outline has R8 corners.

## Deliverables

- `cad/enclosure_assembly.step`: assembled solid geometry, R307 adapter fitted.
- `cad/*.step`: individual editable imported solids; STEP has no native feature tree.
- `cad/*.stl`: individual parts, in assembly coordinates and millimetres. Reorient in slicer.
- `parameters.json` and `build_enclosure.py`: fully editable parameter-driven CAD source.
- `project_cad.py`: orthographic projection of actual imported STEP edges.
- `drawing-geometry.json`: nine views extracted from the current STEP model.
- `../../output/pdf/fingerprint-enclosure-technical-drawing.pdf`: four A3 landscape sheets
  with CAD-derived views, face coordinates, closure details and CAD recreation steps.
- `enclosure-preview.png`: CAD geometry with illustrative display, reader, caps and LEDs.
- `cad/validation.json`: solid validity, STEP round-trip and assembly interference results.

## Fit assumptions

Hardware requested: ESP32, 128x64 I2C OLED, R307 or AS608, DS3231, buzzer,
three push buttons, LEDs, smaller breadboard/Veroboard, external power and
side battery compartment. No measured dimensions were available.

The OLED window assumes a **0.96-inch** variant. Resolution does not determine
physical display size. Waveshare lists a comparable 128x64 display active area
of 21.74 x 11.18 mm; this draft uses a 24 x 13 opening and a conservative
35 x 35 x 12 internal PCB reservation. This is not a claim that your module is
the same Waveshare part.

The R307 adapter has a provisional 20 x 22 window, based on the 19 x 21 optical
window documented by RAKwireless for its GROW R307 module. The AS608 adapter's
15 x 19 opening is an estimate requiring confirmation. The sensor aperture
does not define the module's retention or body dimensions. The 32 x 40 shell
opening accepts either adapter; a measured clamp or bracket is still required.

Reserve a 28-across-face x 60-inward x 35-height envelope for the sensor and
cable. Other reservations and proposed placement are in drawing sheet 4.
The side battery compartment has no modeled cell contacts, charging circuit,
holder retention or regulator. A 25 x 42 x 75 mm pack/holder envelope is proposed;
choose and measure the battery assembly before finalizing the compartment.

Button holes assume 6.5-mm cap/plunger openings, not a particular panel switch.
The button caps in the preview are illustrative. LED holes assume 3-mm LEDs.
The 8-mm rear power opening is provisional and should match a measured connector.

## Coordinate convention

Body axes: x horizontal (main body -75 to +75), y front to rear (0 to 100),
z bottom to top (0 to 100). Battery pod extends x=75 to 115; cover to x=118.
Face coordinates u,v start at its theoretical lower-left corner:
x=u-75, y=0, z=v. The shell floor begins at z=0; its inner surface is z=3.2.
The control panel extends to y=-1.2; sensor adapter to y=-2. The shell rear
ends at y=97; the rear cover completes the main housing to y=100.

## Rebuild

Use Python with `cadquery==2.8.0`, `vtk` (a CadQuery dependency), `pillow` for CAD and preview;
use `reportlab` for the PDF. In this session CAD dependencies were installed in
`C:/Users/Ot/.cache/enclosure-cad/venv`, separate from the backend environment.

```powershell
& 'C:/Users/Ot/.cache/enclosure-cad/venv/Scripts/python.exe' hardware/enclosure/build_enclosure.py
& 'C:/Users/Ot/.cache/enclosure-cad/venv/Scripts/python.exe' hardware/enclosure/project_cad.py --details-dir hardware/enclosure/cad
& 'C:/Users/Ot/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' hardware/enclosure/build_drawing.py
```

Change `parameters.json`, then regenerate CAD, projections, and drawing in order. The outline and
feature parameters are editable; closure hole patterns and support-pad positions
are fixed revision-B coordinates in the source. If enclosure dimensions change,
review these coordinates rather than assuming automatic scaling.

## Before fabrication

This is a layout prototype, not a verified production enclosure. Measure PCB
sizes, mounting patterns, cable bends, sensor orientation, switch travel and
battery holder; add actual board/sensor/switch retention and a cable grommet.
Confirm screw material, engagement and pilot sizes on a printed coupon, and
review print orientation/support requirements. STEP verification only checks
CAD geometry; hardware collisions, thermal performance and physical fit remain
unverified. Four floor pads are provided but no assumed PCB drill pattern.
Illustrative bare-board, sensor/cable and battery envelopes are also checked
against enclosure solids; this does not verify assembled real electronics.
The battery envelope spans x=83..108, y=45..87, z=12..87, avoiding the cover bosses.

## Drawing from a future CAD or Blender file

Use the uploaded file as the geometry source and preserve its proportions.
Confirm units/scale and front/top/right orientation before adding dimensions.
STEP is preferred for exact solids and analytic edges; an imported solid in
STEP does not recover the originating software's feature tree. A Blender mesh
can supply views and dimensions after confirming its scene scale, but faceted
surfaces are not automatically manufacturing-ready CAD surfaces.

The projection utility can already read an independent uploaded STEP:

```powershell
& 'C:/Users/Ot/.cache/enclosure-cad/venv/Scripts/python.exe' hardware/enclosure/project_cad.py --step uploaded.step --output uploaded-views.json
```

Do not pass the current `--details-dir` for another model. The present drawing
layout and annotations are specific to this enclosure and must be adapted
after inspecting any uploaded geometry; projection alone does not assign
hole tolerances, wall thicknesses or functional datum definitions.

## Dimension sources

- [Waveshare OLED module specifications](https://www.waveshare.com/wiki/0.96inch_OLED_Module)
- [RAKwireless GROW R307 specifications](https://store.rakwireless.com/products/rak12001-fingerprint-module)
- [CadQuery STEP export documentation](https://cadquery.readthedocs.io/en/latest/importexport.html)

All enclosure dimensions and other component allowances are provisional design
choices, not measurements extracted from the reference mesh.
