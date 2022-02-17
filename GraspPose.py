# MACRO 1:
# Select part and run it to insert gripper pose (red)
# Select gripper body and run it to insert second pose (pre-gripper, blue) 
# Select pre-gripper body and run it to insert 3D pronter table (green)

def controlled_insert(code):
	a=App.ActiveDocument.Objects
	Part.insert(u"C:/Users/MariaR/Desktop/"+code+".brep",App.ActiveDocument.Name)
	b=App.ActiveDocument.Objects
	return list(set(b) - set(a))[0]

def grip_helper(color):
	b = controlled_insert("B")
	r = controlled_insert("R")
	l = controlled_insert("L")
	b.addProperty("App::PropertyFloat", "GripSize", "Parameter", "Size between fingers")
	b.addProperty("App::PropertyLink", "Container", "Parameter", "Part Container")
	b.addProperty("App::PropertyBool", "IsMainPosition", "Parameter", "Is it main or supportive position")
	b.addProperty("App::PropertyLink", "PartToHandle", "Parameter", "Part to be manipulated by this gripper")
	r.setExpression('.Placement.Base.y', b.Name+'.GripSize / 2')
	l.setExpression('.Placement.Base.y', '-'+b.Name+'.GripSize / 2')
	b.ViewObject.ShapeColor=color
	r.ViewObject.ShapeColor=color
	l.ViewObject.ShapeColor=color
	NewPart = App.activeDocument().addObject('App::Part','Part')
	b.adjustRelativeLinks(NewPart)
	NewPart.addObject(b)
	r.adjustRelativeLinks(NewPart)
	NewPart.addObject(r)
	l.adjustRelativeLinks(NewPart)
	NewPart.addObject(l)
	r.ViewObject.ShowInTree=False
	l.ViewObject.ShowInTree=False
	b.Container=NewPart
	b.ViewObject.Transparency=90
	r.ViewObject.Transparency=90
	l.ViewObject.Transparency=90
	return b


if len(Gui.Selection.getSelection())>0:
	active_body=Gui.Selection.getSelection()[0]
	if "IsMainPosition" in active_body.PropertiesList:
		if active_body.IsMainPosition == False:
			p=controlled_insert("P")
			p.addProperty("App::PropertyLink", "PartToPrint", "Parameter", "Part to be printed on this table")
			p.ViewObject.ShapeColor=(0.0,1.0,0.0,0.0)
			p.PartToPrint=active_body.PartToHandle	
			p.ViewObject.Transparency=90
			p.Placement=active_body.PartToHandle.getGlobalPlacement()
			p.Label = '3D_printer_table_for_'+p.PartToPrint.Name
		else:
			b=grip_helper((0.0,0.0,1.0,0.0))
			b.addProperty("App::PropertyLink", "MainPosition", "Parameter", "Main position")
			b.PartToHandle=active_body.PartToHandle
			b.MainPosition=active_body
			b.IsMainPosition=False
			b.GripSize=b.MainPosition.GripSize
			b.Container.Placement=b.MainPosition.Container.Placement
			b.Container.Label = 'PreGripper_for_'+b.PartToHandle.Name
			tempshape = Part.getShape(b.PartToHandle,'',needSubElement=False,refine=False)
			App.ActiveDocument.addObject('Part::Feature','PartToHandle').Shape=tempshape
			n=App.ActiveDocument.ActiveObject
			n.Label=b.PartToHandle.Label
			n.ViewObject.ShapeColor=(0.0,0.0,1.0,0.0)
			n.adjustRelativeLinks(b.Container)
			b.Container.addObject(n)
			n.Placement.Base = n.getGlobalPlacement().Base.sub(b.Container.Placement)
			n.Placement.Rotation.Axis = n.getGlobalPlacement().Rotation.Axis.sub(b.Container.Placement.Rotation.Axis)
			n.Placement.Rotation.Angle = n.getGlobalPlacement().Rotation.Angle-b.Container.Placement.Rotation.Angle
			n.ViewObject.ShowInTree=False
			n.ViewObject.Transparency=90

	else:
		b=grip_helper((1.0,0.0,0.0,0.0))
		b.addProperty("App::PropertyInteger", "OperationPriority", "Parameter", "Priority of the operation")
		b.addProperty("App::PropertyInteger", "OperationType", "Parameter", "Priority of the operation")
		b.addProperty("App::PropertyFloat", "OperationParameter1", "Parameter", "Priority of the operation")
		b.addProperty("App::PropertyFloat", "OperationParameter2", "Parameter", "Priority of the operation")
		b.addProperty("App::PropertyFloat", "OperationParameter3", "Parameter", "Priority of the operation")
		b.PartToHandle=active_body	
		b.IsMainPosition=True		
		b.GripSize=active_body.Shape.BoundBox.YLength
		b.Container.Placement=active_body.getGlobalPlacement()
		b.Container.Label = 'Gripper_for_'+b.PartToHandle.Name

# MACRO 2:
#Exports all grasp poses to json file

import json  # For exporting part infos
import os    # for safer path handling

if FreeCAD.GuiUp:
    import FreeCADGui
    from PySide import QtGui

opts = QtGui.QFileDialog.DontConfirmOverwrite

ofile, filt = QtGui.QFileDialog.getSaveFileName(None, 'test',
                                                os.getenv("HOME"),
                                                "*.json", options=opts)
odir, of = os.path.split(ofile)
if not os.path.exists(odir):
    os.makedirs(odir)
if not of.lower().endswith(".json"):
    ofile = ofile + ".json"

mp={}

for a in App.ActiveDocument.Objects:
		if "IsMainPosition" in a.PropertiesList:
			pp={}
			pp['Part name'] = a.PartToHandle.Name
			pp['Part label'] = a.PartToHandle.Label

			papb=a.PartToHandle.Placement.Base
			pp['Part position XYZ'] = [papb.x,papb.y,papb.z]
			papa=a.PartToHandle.Placement.Rotation.Axis
			pp['Part rotation axis XYZ'] = [papa.x,papa.y,papa.z]
			pp['Part rotation angle'] = a.PartToHandle.Placement.Rotation.Angle

			apb=a.Container.Placement.Base
			pp['Gripper position XYZ'] = [apb.x,apb.y,apb.z]
			apa=a.Container.Placement.Rotation.Axis
			pp['Gripper rotation axis XYZ'] = [apa.x,apa.y,apa.z]
			pp['Gripper rotation angle'] = a.Container.Placement.Rotation.Angle
			pp['Grip size'] = a.GripSize
			pp['OperationType'] = a.OperationType
			pp['Operation Priority'] = a.OperationPriority
			pp['a.Operation Parameter 1'] = a.OperationParameter1
			pp['a.Operation Parameter 2'] = a.OperationParameter2
			pp['a.Operation Parameter 3'] = a.OperationParameter3
			mp[a.Container.Label]=pp

with open(ofile, "w", encoding="utf8") as propfile:
    json.dump(mp, propfile, indent=1, separators=(',', ': '))

# MACRO 3:
# Select pre-gripper body and run it to animate its movement

from FreeCAD import Base,Placement
import Part
from time import sleep
import PySide

apart=Gui.Selection.getSelection()[0]
sp=apart.Container.Placement.Base
ep=apart.MainPosition.Container.Placement.Base
sa=apart.Container.Placement.Rotation.Angle
ea=apart.MainPosition.Container.Placement.Rotation.Angle
print (sp,ep)

i=0.0
def updatePlacement():
	global timer
	global i
	global sp
	global ep
	global sa
	global ea
	apart.Container.Placement.Base=ep.multiply(i).add(sp.multiply(1.0-i))
	apart.Container.Placement.Rotation.Angle=(ea*i)+(sa*(1.0-i))
	i+=0.02
	if i>=1:
		#apart.Container.Placement.Base=sp
		#apart.Container.Placement.Rotation.Angle=sa
		timer.stop()
	FreeCAD.Gui.updateGui()

timer = PySide.QtCore.QTimer()
timer.timeout.connect(updatePlacement)
timer.start(100)

# MACRO 4:
#Raw advanced version of MACRO 1
#Does not work properly yet

def controlled_insert(code):
	a=App.ActiveDocument.Objects
	Part.insert(u"C:/Users/MariaR/Desktop/"+code+".brep",App.ActiveDocument.Name)
	b=App.ActiveDocument.Objects
	return list(set(b) - set(a))[0]

if len(Gui.Selection.getSelection())>0:
	active_body=Gui.Selection.getSelection()[0]
	b = controlled_insert("B")
	r = controlled_insert("R")
	l = controlled_insert("L")
	b.ViewObject.ShapeColor=(1.0,0.0,0.0,0.0)
	r.ViewObject.ShapeColor=(1.0,0.0,0.0,0.0)
	l.ViewObject.ShapeColor=(1.0,0.0,0.0,0.0)
	b.ViewObject.ShowInTree=False
	r.ViewObject.ShowInTree=False
	l.ViewObject.ShowInTree=False
	b.ViewObject.Transparency=90
	r.ViewObject.Transparency=90
	l.ViewObject.Transparency=90
	a=FreeCAD.ActiveDocument.addObject("App::FeaturePython",'Gripper_for_'+active_body.Name)
	a.addProperty("App::PropertyFloat", "GripSize", "Parameter", "Size between fingers")
	a.addProperty("App::PropertyLink", "PartToHandle", "Parameter", "Part to be manipulated by this gripper")
	a.addProperty("App::PropertyLink", "GripperBody", "Parameter", "Body")
	a.addProperty("App::PropertyLink", "GripperLF", "Parameter", "Body")
	a.addProperty("App::PropertyLink", "GripperRF", "Parameter", "Body")
	a.GripperBody=b
	a.GripperLF=l
	a.GripperRF=r
	#r.setExpression('.Placement.Base.y', a.Name+'.GripSize / 2')
	#l.setExpression('.Placement.Base.y', '-'+a.Name+'.GripSize / 2')
	a.addProperty("App::PropertyInteger", "OperationPriority", "Parameter", "Priority of the operation")
	a.addProperty("App::PropertyInteger", "OperationType", "Parameter", "Priority of the operation")
	a.addProperty("App::PropertyFloat", "OperationParameter1", "Parameter", "Priority of the operation")
	a.addProperty("App::PropertyFloat", "OperationParameter2", "Parameter", "Priority of the operation")
	a.addProperty("App::PropertyFloat", "OperationParameter3", "Parameter", "Priority of the operation")
	a.PartToHandle=active_body	
	a.GripSize=active_body.Shape.BoundBox.YLength

