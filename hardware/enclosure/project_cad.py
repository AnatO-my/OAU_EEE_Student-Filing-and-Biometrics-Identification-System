"""Extract orthographic linework directly from STEP geometry (millimetres).

Can be reused for an uploaded STEP without importing the current CAD generator.
Example: python project_cad.py --step uploaded.step --output uploaded-views.json
For this enclosure, also pass --details-dir cad to include individual parts.
"""
import argparse
import json
from pathlib import Path
import cadquery as cq
from OCP.gp import gp_Ax2,gp_Pnt,gp_Dir
from OCP.HLRBRep import HLRBRep_Algo,HLRBRep_HLRToShape
from OCP.HLRAlgo import HLRAlgo_Projector
from OCP.BRepLib import BRepLib
from OCP.GCPnts import GCPnts_QuasiUniformDeflection


def project(shape, normal, x_direction):
    alg=HLRBRep_Algo();alg.Add(shape.wrapped)
    alg.Projector(HLRAlgo_Projector(gp_Ax2(gp_Pnt(),gp_Dir(*normal),gp_Dir(*x_direction))))
    alg.Update();alg.Hide();result=HLRBRep_HLRToShape(alg)
    polylines=[]
    for raw in (result.VCompound(),result.Rg1LineVCompound(),result.OutLineVCompound()):
        if raw.IsNull():continue
        BRepLib.BuildCurves3d_s(raw,1e-6)
        for edge in cq.Shape(raw).Edges():
            curve=edge._geomAdaptor()
            sample=GCPnts_QuasiUniformDeflection(curve,0.03,curve.FirstParameter(),curve.LastParameter())
            if sample.IsDone():
                points=[[round(sample.Value(i+1).X(),5),round(sample.Value(i+1).Y(),5)]
                        for i in range(sample.NbPoints())]
                if len(points)>1:polylines.append(points)
    points=[p for line in polylines for p in line]
    return {"bounds":[min(p[0] for p in points),min(p[1] for p in points),
                       max(p[0] for p in points),max(p[1] for p in points)],
            "visible_edges":polylines,"normal":normal,"x_direction":x_direction}


def main():
    root=Path(__file__).resolve().parent
    parser=argparse.ArgumentParser()
    parser.add_argument("--step",type=Path,default=root/"cad/enclosure_assembly.step")
    parser.add_argument("--output",type=Path,default=root/"drawing-geometry.json")
    parser.add_argument("--details-dir",type=Path)
    args=parser.parse_args()
    imported=cq.importers.importStep(str(args.step)).vals()
    compound=cq.Compound.makeCompound(imported)
    assert compound.isValid(),"Invalid imported STEP geometry"
    bb=compound.BoundingBox()
    views={"front":project(compound,(0,-1,0),(1,0,0)),
           "top":project(compound,(0,0,1),(1,0,0)),
           "right":project(compound,(1,0,0),(0,1,0)),
           "rear":project(compound,(0,1,0),(-1,0,0))}
    if args.details_dir:
        details={"main_body":((0,-1,0),(1,0,0)),"rear_cover":((0,-1,0),(1,0,0)),
                 "battery_cover":((1,0,0),(0,1,0)),"control_panel":((0,-1,0),(1,0,0)),
                 "sensor_adapter_r307":((0,-1,0),(1,0,0))}
        for name,(normal,xdir) in details.items():
            shape=cq.importers.importStep(str(args.details_dir/f"{name}.step")).val()
            views[name]=project(shape,normal,xdir)
    payload={"source_step":str(args.step.resolve()),"units":"mm", "projection":"orthographic",
             "bounding_box_mm":[round(v,3) for v in (bb.xlen,bb.ylen,bb.zlen)],"views":views}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(payload,separators=(",",":")))
    print(f"Projected {len(views)} views from STEP into {args.output}")


if __name__=="__main__":main()
