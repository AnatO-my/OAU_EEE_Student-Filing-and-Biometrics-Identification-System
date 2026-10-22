"""Revision B: rounded rectangular CAD, millimetres. CadQuery 2.8."""
import json
import math
from pathlib import Path
import cadquery as cq

ROOT = Path(__file__).resolve().parent
P = json.loads((ROOT / "parameters.json").read_text())
OUT = ROOT / "cad"
OUT.mkdir(exist_ok=True)
W, D, H, T, R = (P[k] for k in ("body_width", "depth", "height", "wall", "corner_radius"))
RC, PW, CT = (P[k] for k in ("rear_cover_thickness", "battery_pod_width", "battery_cover_thickness"))
assert P["front_angle_from_vertical_deg"] == 0, "Revision B requires a flat front"


def box(x, y, z, dx, dy, dz):
    return cq.Workplane("XY").box(dx, dy, dz).translate((x, y, z))


def front_plane(u=0, v=0, offset=0):
    return cq.Plane(origin=(-W/2+u, -offset, v), xDir=(1,0,0), normal=(0,-1,0))


def face_rect(center, size, offset=3, thickness=None, radius=0):
    q = cq.Workplane(front_plane(*center, offset)).rect(*size).extrude(-(thickness or T+7))
    return q.edges("|Y").fillet(radius) if radius else q


def face_hole(center, diameter, offset=3, thickness=None):
    return cq.Workplane(front_plane(*center, offset)).circle(diameter/2).extrude(-(thickness or T+7))


def side_profile(x, width, inset=0, radius=R):
    q = cq.Workplane("YZ", origin=(x,D/2,H/2)).rect(D-2*inset,H-2*inset).extrude(width)
    return q.edges("|X").fillet(radius)


def side_hole(x, y, z, diameter, length):
    return cq.Workplane("YZ", origin=(x,y,z)).circle(diameter/2).extrude(length)


# Rounded front outline, small softened front edges, planar rear lid seat.
body = box(0,(D-RC)/2,H/2,W,D-RC,H).edges("|Y").fillet(R)
body = body.faces("<Y").edges().fillet(2)
cavity = box(0,(T+D+5)/2,H/2,W-2*T,D+5-T,H-2*T).edges("|Y").fillet(R-T)
body = body.cut(cavity)
rear = box(0,D-RC/2,H/2,W,RC,H).edges("|Y").fillet(R)
rear = rear.faces(">Y").edges().fillet(0.8)

# Separate left front panel retains the visual layout seen in the references.
control = face_rect(P["control_panel_center_uv"],P["control_panel_size"],
                    offset=P["control_panel_thickness"],thickness=P["control_panel_thickness"],radius=6)
control_cutters = [face_rect(P["oled_center_uv"],P["oled_window"])]
control_cutters += [face_hole(uv,P["button_hole_diameter"]) for uv in P["button_centers_uv"]]
control_cutters += [face_hole(uv,P["led_hole_diameter"]) for uv in P["led_centers_uv"]]
bu,bv = P["buzzer_center_uv"]
for n in range(7):
    uv=(bu,bv) if n==6 else (bu+4*math.cos(n*math.pi/3),bv+4*math.sin(n*math.pi/3))
    control_cutters.append(face_hole(uv,1.6))
for cutter in control_cutters:
    body=body.cut(cutter); control=control.cut(cutter)
control_screws=[(u,v) for u in (11,79) for v in (14,86)]
for uv in control_screws:
    body=body.cut(face_hole(uv,2)); control=control.cut(face_hole(uv,2.4))

body=body.cut(face_rect(P["sensor_center_uv"],P["sensor_body_opening"]))
body=body.cut(face_rect(P["sensor_indicator_center_uv"],[10,3]))
su,sv=P["sensor_center_uv"]
adapter_screws=[(su+du,sv+dv) for du in (-18,18) for dv in (-34,34)]
for uv in adapter_screws: body=body.cut(face_hole(uv,2))


def adapter(window):
    q=face_rect(P["sensor_center_uv"],P["sensor_adapter_size"],offset=2,thickness=2,radius=6)
    q=q.cut(face_rect(P["sensor_center_uv"],window))
    q=q.cut(face_rect(P["sensor_indicator_center_uv"],[10,3]))
    for uv in adapter_screws: q=q.cut(face_hole(uv,2.4))
    return q


# Rear-cover bosses attach to the side walls, leaving the floor accessible.
rear_screws=[(x,z) for x in (-68,68) for z in (12,88)]
for x,z in rear_screws:
    plane=cq.Plane(origin=(x,D-RC,z),xDir=(1,0,0),normal=(0,-1,0))
    body=body.union(cq.Workplane(plane).circle(5.5).extrude(14))
    body=body.cut(cq.Workplane(plane).circle(1.3).extrude(11))
    clearance=cq.Plane(origin=(x,D+1,z),xDir=(1,0,0),normal=(0,-1,0))
    rear=rear.cut(cq.Workplane(clearance).circle(1.7).extrude(RC+2))
for x in (-57,15):
    for y in (46,76): body=body.union(box(x,y,T+2,8,8,4))

# Rear low-voltage power entry, kept on the removable cover.
px,pz=P["power_center_xz"]
power_plane=cq.Plane(origin=(px,D+1,pz),xDir=(1,0,0),normal=(0,-1,0))
rear=rear.cut(cq.Workplane(power_plane).circle(P["power_hole_diameter"]/2).extrude(RC+2))

# Three small slots on the left side, as shown in the side reference.
for z in (32,37,42):
    vent=cq.Workplane("YZ",origin=(-W/2-1,50,z)).rect(25,2).extrude(T+2)
    body=body.cut(vent)

# Rectangular rounded battery pod and recessed grey outer insert.
pod=side_profile(W/2,PW)
pod=pod.cut(side_profile(W/2+T,PW-T+1,T,R-T))
cover=side_profile(W/2+PW,CT)
pod_screws=[(y,z) for y in (7,D-7) for z in (12,88)]
for y,z in pod_screws:
    pod=pod.union(side_hole(W/2+PW-14,y,z,11,14))
    pod=pod.cut(side_hole(W/2+PW-11,y,z,2.6,12))
    cover=cover.cut(side_hole(W/2+PW-1,y,z,3.4,CT+2))
outer_x=W/2+PW+CT
pocket=cq.Workplane("YZ",origin=(outer_x+0.1,D/2,H/2)).rect(80,80).extrude(-0.9).edges("|X").fillet(6)
cover=cover.cut(pocket)
insert=cq.Workplane("YZ",origin=(outer_x-0.8,D/2,H/2)).rect(79.6,79.6).extrude(0.8).edges("|X").fillet(5.8)
body=body.cut(side_hole(W/2-T-1,60,22,8,2*T+2))
pod=pod.cut(side_hole(W/2-1,60,22,8,T+2))
for y,z in ((62,15),(62,85)):
    body=body.cut(side_hole(W/2-T-1,y,z,3.4,T+2))
    pod=pod.cut(side_hole(W/2-1,y,z,2.6,T+2))

parts={"main_body":body,"rear_cover":rear,"control_panel":control,"battery_pod":pod,
       "battery_cover":cover,"battery_cover_insert":insert,
       "sensor_adapter_r307":adapter(P["r307_adapter_window"]),
       "sensor_adapter_as608":adapter(P["as608_adapter_window"])}
colors={"main_body":(0.32,0.39,0.43),"rear_cover":(0.19,0.24,0.29),
        "control_panel":(0.71,0.57,0.78),"battery_pod":(0.96,0.35,0.22),
        "battery_cover":(0.96,0.35,0.22),"battery_cover_insert":(0.25,0.30,0.36),
        "sensor_adapter_r307":(0.19,0.22,0.23)}
assembly=cq.Assembly(name="rectangular_fingerprint_terminal_revision_B")
report={"revision":P["revision"],"units":"mm","parts":{},"intersections_mm3":{}}
assembled_names=list(colors)
for name,q in parts.items():
    shape=q.val()
    assert shape.isValid() and len(q.solids().vals())==1 and shape.Volume()>0,name
    cq.exporters.export(q,str(OUT/f"{name}.step"))
    cq.exporters.export(q,str(OUT/f"{name}.stl"),tolerance=0.08,angularTolerance=0.15)
    imported=cq.importers.importStep(str(OUT/f"{name}.step")).val()
    assert imported.isValid() and abs(imported.Volume()-shape.Volume())<0.01,name
    bb=shape.BoundingBox()
    report["parts"][name]={"valid":True,"solid_count":1,"step_round_trip":True,
                          "volume_mm3":round(shape.Volume(),3),
                          "bounding_box_mm":[round(v,3) for v in (bb.xlen,bb.ylen,bb.zlen)]}
    if name in colors: assembly.add(q,name=name,color=cq.Color(*colors[name]))
for i,name in enumerate(assembled_names):
    for other in assembled_names[i+1:]:
        volume=parts[name].intersect(parts[other]).val().Volume()
        report["intersections_mm3"][name+" / "+other]=round(volume,6)
        assert volume<0.01,(name,other,volume)
assembly.export(str(OUT/"enclosure_assembly.step"))
reservations={"veroboard_plate_only":box(-10,65,8.2,100,50,2),
              "sensor_and_cable":face_rect(P["sensor_center_uv"],[28,35],offset=-T-0.5,thickness=60),
              "battery_pack_holder":box(95.5,66,49.5,25,42,75)}
report["illustrative_reservation_collisions_mm3"]={}
for name,envelope in reservations.items():
    collisions={part:round(envelope.intersect(parts[part]).val().Volume(),6) for part in assembled_names}
    report["illustrative_reservation_collisions_mm3"][name]=collisions
    assert all(volume<0.01 for volume in collisions.values()),(name,collisions)
bb=assembly.toCompound().BoundingBox()
report["assembly_bounding_box_mm"]=[round(v,2) for v in (bb.xlen,bb.ylen,bb.zlen)]
report["status"]="solid geometry verified; hardware fit and manufacture unverified"
(OUT/"validation.json").write_text(json.dumps(report,indent=2))


def render():
    import vtk
    from PIL import Image,ImageDraw,ImageFont
    renderer=vtk.vtkRenderer();renderer.SetBackground(0.96,0.97,0.98)
    def draw(q,color):
        vertices,faces=q.val().tessellate(0.3,0.25)
        points=vtk.vtkPoints()
        for p in vertices: points.InsertNextPoint(p.x,p.y,p.z)
        triangles=vtk.vtkCellArray()
        for face in faces:
            tri=vtk.vtkTriangle()
            for i,idx in enumerate(face):tri.GetPointIds().SetId(i,idx)
            triangles.InsertNextCell(tri)
        data=vtk.vtkPolyData();data.SetPoints(points);data.SetPolys(triangles)
        normals=vtk.vtkPolyDataNormals();normals.SetInputData(data);normals.SetFeatureAngle(30);normals.Update()
        mapper=vtk.vtkPolyDataMapper();mapper.SetInputConnection(normals.GetOutputPort())
        actor=vtk.vtkActor();actor.SetMapper(mapper)
        rgb=tuple(int(color.lstrip("#")[i:i+2],16)/255 for i in (0,2,4)) if isinstance(color,str) else color
        actor.GetProperty().SetColor(*rgb);actor.GetProperty().SetAmbient(0.3);actor.GetProperty().SetDiffuse(0.7)
        renderer.AddActor(actor)
    for name in assembled_names:draw(parts[name],colors[name])
    draw(face_rect(P["oled_center_uv"],[23.6,12.6],offset=1.25,thickness=0.5),"#1ca8d2")
    draw(face_rect(P["sensor_center_uv"],[19.6,21.6],offset=2.05,thickness=0.5),"#284890")
    draw(face_rect(P["sensor_indicator_center_uv"],[9.6,2.6],offset=2.05,thickness=0.5),"#3280ff")
    for uv in P["button_centers_uv"]:draw(cq.Workplane(front_plane(*uv,2.4)).circle(2.8).extrude(-2),"#41454c")
    for uv,color in zip(P["led_centers_uv"],["#42c487","#eead39","#e15d65"]):
        draw(cq.Workplane(front_plane(*uv,2)).circle(1.5).extrude(-1),color)
    camera=renderer.GetActiveCamera();camera.SetPosition(285,-370,200);camera.SetFocalPoint(17,45,48)
    camera.SetViewUp(0,0,1);camera.ParallelProjectionOn();camera.SetParallelScale(112)
    window=vtk.vtkRenderWindow();window.SetOffScreenRendering(1);window.SetSize(1800,1040)
    window.AddRenderer(renderer);window.SetMultiSamples(8);renderer.ResetCameraClippingRange();window.Render()
    cap=vtk.vtkWindowToImageFilter();cap.SetInput(window);cap.Update()
    writer=vtk.vtkPNGWriter();writer.SetInputConnection(cap.GetOutputPort())
    writer.SetFileName(str(ROOT/"enclosure-preview.png"));writer.Write();window.Finalize()
    im=Image.open(ROOT/"enclosure-preview.png").convert("RGB");d=ImageDraw.Draw(im)
    font_path=ROOT.parents[1]/"docs/fonts/FunnelDisplay-Regular.ttf"
    if not font_path.exists():font_path=Path("C:/Windows/Fonts/arial.ttf")
    title=ImageFont.truetype(str(font_path),36);small=ImageFont.truetype(str(font_path),23)
    d.text((60,40),"FINGERPRINT TERMINAL / RECTANGULAR CAD DRAFT B",font=title,fill="#253641")
    d.text((60,95),"Flat front | 150 x 100 x 100 main housing | 193 x 102 x 100 overall with panels",font=small,fill="#536672")
    d.text((60,990),"Approximate layout. Reference proportions adapted for three buttons; hardware fit requires measurement.",font=small,fill="#536672")
    im.save(ROOT/"enclosure-preview.png")


render()
print(json.dumps(report,indent=2))
