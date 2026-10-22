"""A3 drawing with orthographic edge linework extracted from exported STEP."""
import json
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.colors import HexColor, white

ROOT=Path(__file__).resolve().parent
P=json.loads((ROOT/"parameters.json").read_text())
G=json.loads((ROOT/"drawing-geometry.json").read_text())
OUT=ROOT.parents[1]/"output/pdf/fingerprint-enclosure-technical-drawing.pdf"
OUT.parent.mkdir(parents=True,exist_ok=True)
PW,PH=landscape(A3)
C=canvas.Canvas(str(OUT),pagesize=(PW,PH))
C.setTitle("Rectangular fingerprint enclosure - technical drawing, revision B")
NAVY,GREY,ORANGE=map(HexColor,["#233b4c","#687d89","#e56a43"])


def text(x,y,value,size=11,bold=False,color=NAVY):
    C.setFillColor(color);C.setFont("Helvetica-Bold" if bold else "Helvetica",size)
    C.drawString(x,y,str(value))


def line(x1,y1,x2,y2,color=NAVY,width=0.8,dash=None):
    C.setStrokeColor(color);C.setLineWidth(width);C.setDash(dash or [])
    C.line(x1,y1,x2,y2);C.setDash([])


def rect(x,y,w,h,color=NAVY,fill=None):
    C.setStrokeColor(color);C.setLineWidth(1);C.setFillColor(fill or white)
    C.rect(x,y,w,h,stroke=1,fill=bool(fill))


def dimh(x1,x2,object_y,y,label):
    for x in (x1,x2):line(x,object_y,x,y+(5 if y>object_y else -5),GREY,0.4)
    line(x1,y,x2,y,GREY,0.5)
    for x in (x1,x2):line(x-3,y-3,x+3,y+3,GREY,0.6)
    tw=C.stringWidth(label,"Helvetica",10)
    C.setFillColor(white);C.rect((x1+x2-tw)/2-3,y-2,tw+6,13,fill=1,stroke=0)
    text((x1+x2-tw)/2,y+1,label,10)


def dimv(y1,y2,object_x,x,label):
    for y in (y1,y2):line(object_x,y,x+(5 if x>object_x else -5),y,GREY,0.4)
    line(x,y1,x,y2,GREY,0.5)
    for y in (y1,y2):line(x-3,y-3,x+3,y+3,GREY,0.6)
    C.saveState();C.translate(x-4,(y1+y2)/2);C.rotate(90)
    tw=C.stringWidth(label,"Helvetica",10)
    C.setFillColor(white);C.rect(-tw/2-3,-2,tw+6,13,fill=1,stroke=0)
    text(-tw/2,1,label,10);C.restoreState()


def note(x,y,lines,size=11,leading=18):
    for i,s in enumerate(lines):text(x,y-i*leading,s,size)


def table(x,y,widths,rows,height=26):
    for r,row in enumerate(rows):
        xx=x
        for w,value in zip(widths,row):
            rect(xx,y-(r+1)*height,w,height,GREY,HexColor("#eef3f5") if r==0 else None)
            text(xx+8,y-(r+1)*height+9,value,10,r==0);xx+=w


def header(page,title,scale):
    rect(24,24,PW-48,PH-48,GREY)
    text(44,PH-57,"EEE / FINGERPRINT TERMINAL",17,True)
    text(44,PH-82,title,12)
    text(PW-350,PH-57,"REV B | 07 OCT 2026",11,True)
    text(PW-350,PH-78,"APPROXIMATE - VERIFY HARDWARE FIT",10,True,ORANGE)
    line(24,PH-98,PW-24,PH-98,GREY);line(24,68,PW-24,68,GREY)
    text(44,45,"Units: mm | "+scale+" | A3 landscape | Use written dimensions; print at 100%.",10)
    text(PW-185,45,f"SHEET {page} OF 4",10,True)


def cadview(name,x,y,s=2,color=NAVY):
    """Plot only actual visible STEP edges; no hand-drawn silhouette."""
    view=G["views"][name];xmin,ymin,xmax,ymax=view["bounds"]
    C.setStrokeColor(color);C.setLineWidth(0.65)
    for edge in view["visible_edges"]:
        path=C.beginPath();path.moveTo(x+(edge[0][0]-xmin)*s,y+(edge[0][1]-ymin)*s)
        for xx,yy in edge[1:]:path.lineTo(x+(xx-xmin)*s,y+(yy-ymin)*s)
        C.drawPath(path)
    return (xmax-xmin)*s,(ymax-ymin)*s


# Sheet 1: edge linework comes from the reopened assembled STEP.
header(1,"ROUNDED RECTANGULAR ENCLOSURE / ORTHOGRAPHIC VIEWS","Views 1:1.417; preview NTS")
x=110;y=445;s=2
w,h=cadview("top",x,y,s)
text(x,y+h+51,"TOP VIEW",12,True)
dimh(x,x+150*s,y+h,y+h+27,"150 main housing")
dimh(x,x+w,y,y-31,"193 assembled width")
dimv(y,y+h,x,x-36,"102 incl. front trim")
x=110;y=135
w,h=cadview("front",x,y,s)
text(x,y+h+30,"FRONT VIEW / FLAT FACE",12,True)
dimh(x,x+w,y,y-30,"193")
dimv(y,y+h,x,x-36,"100 height")
x=760;y=135
w,h=cadview("right",x,y,s)
text(x,y+h+30,"RIGHT VIEW / BATTERY COVER",12,True)
dimh(x,x+w,y,y-30,"102 incl. front trim")
dimv(y,y+h,x+w,x+w+28,"100")
C.drawImage(str(ROOT/"enclosure-preview.png"),590,433,width=545,height=294,preserveAspectRatio=True,anchor="c")
note(590,411,["Body front and rear are parallel; front slope is 0 deg.",
              "Main housing nominal 150 W x 100 D x 100 H (rear lid included).",
              "Battery pod 40 wide plus 3-thick outer cover; front panel projects 2."],10,16)
C.showPage()

# Sheet 2: body cutouts, panel sizes and measured-coordinate convention.
header(2,"FRONT CUTOUTS / PANEL LAYOUT","Front body view 1:1; all positions in flat face plane")
x=108;y=235;s=72/25.4
w,h=cadview("main_body",x,y,s)
text(x,y+h+65,"BODY FRONT / TRIM PANELS OMITTED",12,True)
dimh(x,x+w,y+h,y+h+28,"150")
dimv(y,y+h,x,x-38,"100")
line(x-12,y,x+25,y,ORANGE,1.2);line(x,y-12,x,y+25,ORANGE,1.2)
text(x-5,y-28,"DATUM: theoretical lower-left body corner",10,True,ORANGE)
text(x+190,y-49,"u -> right; v -> up; x=u-75, z=v",10)
rows=[["Feature","Center u, v","Opening / pattern"],
      ["OLED window","46, 72","24 x 13"],
      ["Sensor body cutout","117, 50","32 x 40"],
      ["Sensor indicator","117, 77","10 x 3"],
      ["Adapter pilots","99/135, 16/84","4 x DIA 2.0"],
      ["Buttons (3)","26/46/66, 29","3 x DIA 6.5"],
      ["LEDs (3)","35/46/57, 48","3 x DIA 3.2"],
      ["Buzzer grille","46, 16","7 x DIA 1.6; 6 on DIA 8 PCD"],
      ["Control pilots","11/79, 14/86","4 x DIA 2.0"]]
table(610,632,[135,145,225],rows)
note(610,369,["Left control panel: 80 W x 84 H x 1.2 thick; corners R6.",
              "Center u=45, v=50; extents u=5..85, v=8..92.",
              "Tall sensor adapter: 44 W x 80 H x 2 thick; corners R6.",
              "Center u=117, v=50; extents u=95..139, v=10..90.",
              "Panel clearance holes DIA 2.4; body pilots DIA 2.0.",
              "Cut openings normal to the flat front through the wall.",
              "OLED assumes 0.96-inch active area; resolution alone",
              "does not specify module size. Verify before cutting.",
              "Button holes assume small caps or custom plungers.",
              "Add measured brackets for sensor, OLED and switches."],11,21)
text(610,121,"Dimension references: Waveshare OLED specs | RAKwireless GROW R307 specs",9)
C.linkURL("https://www.waveshare.com/wiki/0.96inch_OLED_Module",(700,118,826,132),relative=0)
C.linkURL("https://store.rakwireless.com/products/rak12001-fingerprint-module",(835,118,1106,132),relative=0)
C.showPage()

# Sheet 3: real projected detail parts and their attachment patterns.
header(3,"REAR COVER / BATTERY COVER / SENSOR ADAPTER","Details 1:1.417; dimensions are nominal")
x=92;y=413;s=2
w,h=cadview("rear_cover",x,y,s)
text(x,y+h+55,"REAR COVER / INNER VIEW",12,True)
dimh(x,x+w,y+h,y+h+25,"150")
dimv(y,y+h,x,x-35,"100")
note(x,y-27,["Cover 3 thick; front-outline corners R8.",
             "4 x DIA 3.4; body pilots DIA 2.6, depth 11.",
             "Screw x=-68/+68; z=12/88 (body axes).",
             "Rear boss OD 11, length 14, toward front.",
             "Power entry DIA 8 at x=-45, z=25."],10,17)
x=538;y=413
w,h=cadview("battery_cover",x,y,s,ORANGE)
text(x,y+h+55,"BATTERY COVER / OUTER VIEW",12,True)
dimh(x,x+w,y,y-25,"100 depth")
dimv(y,y+h,x+w,x+w+30,"100 height")
note(x,y-54,["Cover 3 thick; corners R8.",
             "4 x DIA 3.4 at y=7/93, z=12/88.",
             "Pod bosses OD 11 x 14; pilots DIA 2.6 x 11.",
             "Centered insert recess 80 x 80 x 0.8 deep, R6.",
             "Insert 79.6 x 79.6 x 0.8, R5.8.",
             "Insert has 0.2 edge gap; bonded cosmetic panel."],10,17)
x=902;y=421
w,h=cadview("sensor_adapter_r307",x,y,s)
text(x-30,y+h+44,"SENSOR ADAPTER",12,True)
dimh(x,x+w,y,y-24,"44")
dimv(y,y+h,x+w,x+w+25,"80")
note(858,366,["Plate 2 thick; corners R6.",
              "4 x DIA 2.4; pitch 36 x 68.",
              "Hole offsets from edges: 4, 6.",
              "R307 window: 20 x 22 at plate center.",
              "AS608 window: 15 x 19 at plate center.",
              "Indicator: 10 x 3; center 27 above",
              "plate center (optional LED/light pipe)."],10,17)
line(70,224,PW-70,224,GREY)
note(80,198,["COMMON DETAILS",
             "Main front outline R8, front edge roll R2; rear-cover exposed edge R0.8. Wall 3.2 nominal; front plate corners R6.",
             "Pod attachment: y=62, z=15/85; body DIA 3.4 clearance, pod DIA 2.6 pilot. Wire passage DIA 8 at y=60, z=22.",
             "Three left-side vents: 25 x 2; centers y=50, z=32/37/42. Add cable edge protection at the inter-compartment passage.",
             "Floor pads: 8 x 8 x 4 high above 3.2 floor; centers x=-57/+15, y=46/76. PCB retention requires measured holes/clips.",
             "Pilot sizes are provisional for printed plastic. Check screw type, engagement and fit with a small printed coupon."],11,19)
C.showPage()

# Sheet 4: allowances and future imported geometry workflow.
header(4,"SPACE ALLOWANCES / CAD RECREATION & IMPORT WORKFLOW","Component allowances NTS; hardware fit unverified")
rows=[["Item","Provisional reservation (mm)","Fit / retention action"],
      ["ESP32 development board","60 x 35 x 20","Measure board variant, antenna and USB access"],
      ["0.96-inch OLED PCB","35 x 35 x 12","Confirm display opening and screw pattern"],
      ["R307 / AS608 + cable","28 across x 60 inward x 35 height","Measure module/cable bend; add clamp"],
      ["DS3231 breakout","40 x 26 x 12","Keep coin-cell holder accessible"],
      ["Buzzer / switches","DIA 15 x 12 / 12 x 12 x 15 each","Match caps, travel, grille and retention"],
      ["Veroboard / small breadboard","100 x 50 plan","Use left floor zone; measure and secure board"],
      ["Battery holder + pack","25 across x 42 depth x 75 height","Choose holder/regulation/charge hardware"]]
table(60,704,[160,340,560],rows,29)
text(60,439,"INTERNAL LAYOUT",12,True)
note(60,411,["Veroboard: x=-60..40, y=40..90; pads top z=7.2. Proposed 2-thick board occupies z=7.2..9.2.",
             "Sensor envelope: x=28..56, y=3.7..63.7, z=32.5..67.5; keep tall parts out of this zone.",
             "Battery envelope: x=83..108, y=45..87, z=12..87, avoiding the battery-cover bosses.",
             "These three simple envelopes clear the enclosure solids; actual boards, plugs and brackets are unverified."],11,21)
text(60,303,"RECREATE THE RECTANGULAR ENCLOSURE",12,True)
note(60,275,["1. Set mm. Main shell: 150 W x 97 D x 100 H; front outline R8, front edge R2. Rear cover adds 3 depth.",
             "2. Hollow with 3.2 front/floor/top/side walls and open rear. Add rear screw bosses and four floor pads.",
             "3. Sketch sheet-2 cutouts on the vertical front; add separate 80 x 84 control panel and 44 x 80 sensor adapter.",
             "4. Make a 40 x 100 x 100 pod with rounded side corners R8; hollow to outer side and add sheet-3 cover/insert.",
             "5. Add vents, rear power entry, attachment holes and wiring passage. Check measured hardware and print tolerances."],10,18)
text(60,161,"WHEN YOU PROVIDE A CAD OR BLENDER FILE",12,True)
note(60,136,["Use its geometry as the drawing source. STEP is preferred for solids; Blender/mesh exports need confirmed scale and axes.",
             "The included project_cad.py already extracts orthographic edges from imported STEP. Uploaded geometry will be inspected",
             "before adding dimensions, sections and manufacturing details; screenshot perspective will not define the finished shape."],10,17)
C.showPage();C.save();print(OUT)
