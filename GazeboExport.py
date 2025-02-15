import FreeCAD, Mesh, os, numpy as np
import yaml
import argparse
import collada
from xml.etree import ElementTree as ET
from xml.dom.minidom import parseString
from math import radians as _radians
import Part

# Takes subassembly or parts dictionary { part_label: { "obj": <obj>, "mesh": <meshuri> } }
# and generate SDF for them

def export_sdf(objects, export_dir, modelname, configs={}):
    model_dir = os.path.join(export_dir, modelname)

    scale = configs.get('scale', 0.001)
    scale_vec = FreeCAD.Vector([scale]*3)
    density = configs.get('density', 1000)

    shapes = list(map(lambda x: x["obj"].Shape, objects.values()))
    bounding_box = Part.makeCompound(shapes).BoundBox
    bounding_box.scale(*scale_vec)
    global_pose_base = FreeCAD.Vector(bounding_box.XLength/2,
                                 bounding_box.YLength/2,
                                 bounding_box.ZLength/2)
    global_pose_base -= bounding_box.Center
    global_pose = FreeCAD.Placement()
    global_pose.Base = global_pose_base

    model = Model(name=modelname, pose=global_pose)
    model.self_collide = False
    model.sdf_version = '1.5'

    for label in objects.keys():
        shape = objects[label]["obj"].Shape
        mass = shape.Mass * scale**3 * density
        com = shape.CenterOfMass * scale
        inr = shape.MatrixOfInertia
        inr.scale(*scale_vec*(scale**4) * density)
        placement = shape.Placement
        placement.Base.scale(*scale_vec)
        pose = placement.copy()
        pose.Base = com
        pose_rpy = pose.copy()
        pose_rpy.Base=(np.zeros(3))
        inertia = Inertia(inertia=np.array(inr.A)[[0,1,2,5,6,10]])
        inertial = Inertial(pose=pose_rpy, mass=mass, inertia=inertia)

        mesh_uri = os.path.normpath(os.path.relpath(objects[label]["mesh"], export_dir))
        visual = Visual(name=label+'_visual', mesh=mesh_uri)
        collision = Collision(name=label+'_collision', mesh=mesh_uri)

        link = Link(name=label,
                    pose=pose,
                    inertial=inertial,
                    visual=visual,
                    collision=collision)
        model.links.append(link)

    with open(os.path.join(model_dir, 'model.sdf'), 'w') as sdf_file:
        sdf_file.write(model.to_xml_string('sdf'))

###################################################################
# Export helpers
###################################################################



def export_collada(exportList, filename, scale=0.001, quality=1, offset=np.zeros(3)):
    '''FreeCAD collada exporter
    exportList - list of objects
    scale - scaling factor for the mesh
    quality - mesh tessellation quality
    offset - offset of the origin of the resulting mesh'''

    colmesh = collada.Collada()
    colmesh.assetInfo.upaxis = collada.asset.UP_AXIS.Z_UP
    objind = 0
    scenenodes = []

    for obj in exportList:
        bHandled = False
        if obj.isDerivedFrom("Part::Feature"):
            bHandled = True
            m = obj.Shape.tessellate(quality)
            vindex = []
            nindex = []
            findex = []
            # vertex indices
            for v in m[0]:
                vindex.extend([a*scale+b for a, b in zip(v, offset)])
            # normals
            for f in obj.Shape.Faces:
                n = f.normalAt(0,0)
                for i in range(len(f.tessellate(quality)[1])):
                    nindex.extend([n.x,n.y,n.z])
            # face indices
            for i in range(len(m[1])):
                f = m[1][i]
                findex.extend([f[0],i,f[1],i,f[2],i])
        elif obj.isDerivedFrom("Mesh::Feature"):
            bHandled = True
            print("exporting mesh ",obj.Name, obj.Mesh)
            m = obj.Mesh
            vindex = []
            nindex = []
            findex = []
            # vertex indices
            for v in m.Topology[0]:
                vindex.extend([a*scale+b for a, b in zip(v, offset)])
            # normals
            for f in m.Facets:
                n = f.Normal
                nindex.extend([n.x,n.y,n.z])
            # face indices
            for i in range(len(m.Topology[1])):
                f = m.Topology[1][i]
                findex.extend([f[0],i,f[1],i,f[2],i])

        if bHandled:
            vert_src = collada.source.FloatSource("cubeverts-array"+str(objind),
                                                  np.array(vindex),
                                                  ('X', 'Y', 'Z'))
            normal_src = collada.source.FloatSource("cubenormals-array"+str(objind),
                                                    np.array(nindex),
                                                    ('X', 'Y', 'Z'))
            geom = collada.geometry.Geometry(colmesh,
                                             "geometry"+str(objind),
                                             obj.Label,
                                             [vert_src, normal_src])

            input_list = collada.source.InputList()
            input_list.addInput(0, 'VERTEX', "#cubeverts-array"+str(objind))
            input_list.addInput(1, 'NORMAL', "#cubenormals-array"+str(objind))
            triset = geom.createTriangleSet(np.array(findex),
                                            input_list,
                                            "materialref")
            geom.primitives.append(triset)
            colmesh.geometries.append(geom)

            geomnode = collada.scene.GeometryNode(geom)
            node = collada.scene.Node("node"+str(objind), children=[geomnode])

            #TODO: Add materials handling
            scenenodes.append(node)

        objind += 1

    scene = collada.scene.Scene("scene", scenenodes)
    colmesh.scenes.append(scene)
    colmesh.scene = scene

    colmesh.write(filename)
    print("file %s successfully created\n" % filename)


###################################################################
# Conversion Helpers
###################################################################

def deg2rad(d):
    '''Converts degrees to radians'''
    return _radians(d)

def flt2str(f):
    '''Converts floats to formatted string'''
    return '{:.6f}'.format(f)


###################################################################
# Model Helpers
###################################################################

def add_poses(p1, p2):
    return FreeCAD.Placement(p1.toMatrix() + p2.toMatrix())

def subtract_poses(p1, p2):
    return FreeCAD.Placement(p1.toMatrix() + p2.toMatrix().inverse())

def pose_to_xml(pose, fmt='sdf'):
    '''Converts a pose/freecad placement/ to xml element
    with tag "pose" for sdf and "origin" for urdf'''
    xyz = pose.Base
    rpy = pose.Rotation.toEuler()

    if fmt == 'urdf':
        args = {'xyz': ' '.join([flt2str(i) for i in xyz]),
                'rpy': ' '.join([flt2str(deg2rad(j)) for j in rpy])}
        return ET.Element('origin', args)

    pose_elem = ET.Element('pose')
    pose_elem.text = ' '.join([flt2str(i) for i in xyz]
                              + [flt2str(deg2rad(j)) for j in rpy])

    return pose_elem

def pose_xyz(pose):
    '''Returns the xyz/Base portion of a pose as string'''
    xyz = pose.Base if hasattr(pose, 'Base') else pose
    return ' '.join([flt2str(i) for i in xyz])

def config(model_name, sdf, author, email, desc, version):
    top = ET.Element('model')
    name = ET.SubElement(top, 'name')
    name.text = model_name
    ver = ET.SubElement(top, 'version')
    ver.text = version
    sdf_file = ET.SubElement(top, 'sdf')
    sdf_file.text = sdf
    sdf_file.set('version', '1.5')

    author_tag = ET.SubElement(top, 'author')
    author_name = ET.SubElement(author_tag, 'name')
    author_name.text = author
    email_address = ET.SubElement(author_tag, 'email')
    email_address.text = email

    description = ET.SubElement(top, 'description')
    description.text = desc

    dom = parseString(ET.tostring(top, encoding="unicode"))
    return dom.toprettyxml(indent=' '*2)


class SpatialEntity(object):
    '''A base class for sdf/urdf elements containing name, pose and urdf_pose'''
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', '')
        self.pose = kwargs.get('pose', FreeCAD.Placement())
        self.global_pose = kwargs.get('global_pose', FreeCAD.Placement())
        self.urdf_pose = kwargs.get('urdf_pose', FreeCAD.Placement())

        self.formats = ['sdf', 'urdf']

    def to_xml(self, fmt='sdf'):
        '''Call this to check if a format is supported or not'''
        if not fmt in self.formats:
            raise Exception('Invalid export format')


class Model(SpatialEntity):
    '''A class representing a model/robot'''
    def __init__(self, **kwargs):
        super(Model, self).__init__(**kwargs)
        self.static = kwargs.get('static', False)
        self.self_collide = kwargs.get('self_collide', False)
        self.sdf_version = kwargs.get('sdf_version', 1.5)

        self.links = []
        self.joints = []

        if 'link' in kwargs:
            self.links.append(kwargs.get('link', Link()))
        self.links.extend(kwargs.get('links', []))

        if 'joint' in kwargs:
            self.joints.append(kwargs.get('joint', Joint()))
        self.joints.extend(kwargs.get('joints', []))

    def get_link(self, link_name):
        for link in self.links:
            if link_name == link.name:
                return link

    def get_joint(self, joint_name):
        pass

    def get_root_link(self):
        root_link = None
        for link in self.links:
            if not link.parent_joint:
                root_link = link
        return root_link

    def build_tree(self):
        for joint in self.joints:
            joint.parent_link = self.get_link(joint.parent)
            if not joint.parent_link:
                raise Exception('Parent not found for joint %s' % joint.name)
            joint.parent_link.child_joints.append(joint)

            joint.child_link = self.get_link(joint.child)
            if not joint.child_link:
                raise Exception('Child not found for joint %s' % joint.name)
            joint.child_link.parent_joint = joint

    def calculate_global_poses(self):
        for link in self.links:
            link.global_pose = add_poses(self.pose, link.pose)
        for joint in self.joints:
            joint.global_pose = add_poses(joint.child_link.global_pose, joint.pose)

    def to_xml(self, fmt='sdf'):
        '''returns xml element of a model/robot'''
        super(Model, self).to_xml(fmt)

        self.build_tree()
        self.calculate_global_poses()

        tag = 'robot' if fmt=='urdf' else 'model'
        model = ET.Element(tag, name=self.name)

        if fmt == 'sdf':
            model.append(pose_to_xml(self.pose))
            static = ET.SubElement(model, 'static')
            static.text = str(self.static).lower()
            self_collide = ET.SubElement(model, 'self_collide')
            self_collide.text = str(self.self_collide).lower()
        else:
            model.set('static', str(self.static).lower())

            root_link = self.get_root_link()
            if not root_link:
                raise Exception("Couldn't find root link")
            model.append(ET.Element('link', name=root_link.name+'_root'))
        for link in self.links:
            model.append(link.to_xml(fmt))

        if fmt=='urdf':
            root_joint = ET.Element('joint',
                                    {"name": root_link.name+'_root',
                                     "type": "fixed"})
            root_joint.append(pose_to_xml(root_link.global_pose, fmt))
            ET.SubElement(root_joint, 'parent', link= root_link.name+'_root')
            ET.SubElement(root_joint, 'child', link= root_link.name)
            model.append(root_joint)

        for joint in self.joints:
            model.append(joint.to_xml(fmt))

        if fmt == 'sdf':
            sdf = ET.Element('sdf', version=str(self.sdf_version))
            sdf.append(model)
            return sdf

        return model

    def to_xml_string(self, fmt='sdf', header=True):
        dom = parseString(ET.tostring(self.to_xml(fmt)))
        return dom.toprettyxml(indent=' '*2)


class Inertia(object):
    '''A clss representing an inertia element'''
    def __init__(self, **kwargs):
        self.ixx = kwargs.get('ixx', 0)
        self.ixy = kwargs.get('ixy', 0)
        self.ixz = kwargs.get('ixz', 0)
        self.iyy = kwargs.get('iyy', 0)
        self.iyz = kwargs.get('iyz', 0)
        self.izz = kwargs.get('izz', 0)
        if 'inertia' in kwargs:
            self.ixx, self.ixy, self.ixz = kwargs.get('inertia', [0]*6)[:3]
            self.iyy, self.iyz, self.izz = kwargs.get('inertia', [0]*6)[3:]
        self.coords = 'ixx', 'ixy', 'ixz', 'iyy', 'iyz', 'izz'

    def to_xml(self, fmt='sdf'):
        '''returns inetria xml element'''
        inertia = ET.Element('inertia')
        for coord in self.coords:
            if fmt == 'sdf':
                elem = ET.SubElement(inertia, coord)
                elem.text = flt2str(getattr(self, coord, 0))
            else:
                inertia.set(coord, flt2str(getattr(self, coord, 0)))
        return inertia


class Inertial(SpatialEntity):
    '''A class representing an inertial element'''
    def __init__(self, **kwargs):
        super(Inertial, self).__init__(**kwargs)
        self.mass = kwargs.get('mass', 0)
        self.inertia = kwargs.get('inertia', Inertia())

    def to_xml(self, fmt='sdf'):
        '''returns inertial xml element'''
        super(Inertial, self).to_xml(fmt)
        inertial = ET.Element('inertial')
        pose = self.pose if fmt=='sdf' else self.urdf_pose
        inertial.append(pose_to_xml(pose, fmt=fmt))
        mass = ET.SubElement(inertial, 'mass')
        if fmt == 'sdf':
            mass.text = flt2str(self.mass)
        else:
            mass.set('value', flt2str(self.mass))
        inertial.append(self.inertia.to_xml(fmt=fmt))

        return inertial


class Geom(SpatialEntity):
    '''A base class for collision and visual classes'''
    def __init__(self, **kwargs):
        super(Geom, self).__init__(**kwargs)
        self.mesh = kwargs.get('mesh', '')
        self.type = kwargs.get('type', 'visual')

    def to_xml(self, fmt='sdf'):
        '''returns visual or collision xml element'''
        super(Geom, self).to_xml(fmt)
        elem = ET.Element(self.type, name=self.name)
        pose = self.pose if fmt=='sdf' else self.urdf_pose
        elem.append(pose_to_xml(pose, fmt=fmt))
        geom = ET.SubElement(elem, 'geometry')
        mesh = ET.SubElement(geom, 'mesh')
        if fmt=='urdf':
            mesh.set('filename', 'package://' + self.mesh)
        else:
            uri = ET.SubElement(mesh, 'uri')
            uri.text = 'model://' + self.mesh

        return elem


class Visual(Geom):
    '''A class representing a visual element'''
    def __init__(self, **kwargs):
        super(Visual, self).__init__(type='visual', **kwargs)


class Collision(Geom):
    '''A class representing a collision element'''
    def __init__(self, **kwargs):
        super(Collision, self).__init__(type='collision', **kwargs)


class Link(SpatialEntity):
    '''A class representing a link element'''
    def __init__(self, **kwargs):
        super(Link, self).__init__(**kwargs)
        self.inertial = kwargs.get('inertial', Inertial())
        self.visuals = []
        self.collisions = []

        self.parent_joint = None
        self.child_joints = []

        if 'visual' in kwargs:
            self.visuals.append(kwargs.get('visual', Visual()))
        self.visuals.extend(kwargs.get('visuals', []))

        if 'collision' in kwargs:
            self.visuals.append(kwargs.get('collision', Collision()))
        self.collisions.extend(kwargs.get('collisions', []))

    def to_xml(self, fmt='sdf'):
        '''returns link xml element'''
        super(Link, self).to_xml(fmt)
        link = ET.Element('link', name=self.name)

        if self.parent_joint:
            self.urdf_pose = subtract_poses(self.global_pose,
                                           self.parent_joint.global_pose)
        else:
            self.urdf_pose = FreeCAD.Placement()

        if fmt == 'sdf':
            link.append(pose_to_xml(self.pose, fmt=fmt))

        self.inertial.urdf_pose = add_poses(self.inertial.pose, self.urdf_pose)
        link.append(self.inertial.to_xml(fmt=fmt))

        for visual in self.visuals:
            visual.urdf_pose = self.urdf_pose.copy()
            link.append(visual.to_xml(fmt=fmt))
        for collision in self.collisions:
            collision.urdf_pose = self.urdf_pose.copy()
            link.append(collision.to_xml(fmt=fmt))

        return link


class Axis(SpatialEntity):
    '''A class representing an axis element'''
    def __init__(self, **kwargs):
        super(Axis, self).__init__(**kwargs)
        self.lower_limit = kwargs.get('lower_limit', 0)
        self.upper_limit = kwargs.get('upper_limit', 0)
        self.effort_limit = kwargs.get('effort_limit', 0)
        self.velocity_limit = kwargs.get('velocity_limit', 0)
        self.friction = kwargs.get('friction', 0)
        self.damping = kwargs.get('damping', 0)
        self.use_parent_frame = kwargs.get('use_parent_frame', False)

    def to_xml(self, fmt='sdf'):
        '''returns an axis xml element for sdf
        or an array of axis and limit xml elements for urdf'''
        super(Axis, self).to_xml(fmt)

        axis = ET.Element('axis')
        if fmt=='sdf':
            xyz = ET.SubElement(axis, 'xyz')
            xyz.text = pose_xyz(self.pose)
            limit = ET.SubElement(axis, 'limit')
            lower = ET.SubElement(limit, 'lower')
            lower.text = flt2str(deg2rad(self.lower_limit))
            upper = ET.SubElement(limit, 'upper')
            upper.text = flt2str(deg2rad(self.upper_limit))
            effort = ET.SubElement(limit, 'effort')
            effort.text = flt2str(self.effort_limit)
            velocity = ET.SubElement(limit, 'velocity')
            velocity.text = flt2str(self.velocity_limit)
            dynamics = ET.SubElement(axis, 'dynamics')
            friction = ET.SubElement(dynamics, 'friction')
            friction.text = flt2str(self.friction)
            damping = ET.SubElement(dynamics, 'damping')
            damping.text = flt2str(self.damping)
            use_parent_frame = ET.SubElement(axis, 'use_parent_model_frame')
            use_parent_frame.text = str(self.use_parent_frame).lower()
        else:
            axis.set('xyz', pose_xyz(self.pose))
            axis.set('use_parent_model_frame', str(self.use_parent_frame).lower())
            limit = ET.Element('limit')
            limit.set('lower', flt2str(deg2rad(self.lower_limit)))
            limit.set('upper', flt2str(deg2rad(self.upper_limit)))
            limit.set('effort', flt2str(self.effort_limit))
            limit.set('velocity', flt2str(self.velocity_limit))

            dynamics = ET.Element('dynamics')
            dynamics.set('friction', flt2str(self.friction))
            dynamics.set('damping', flt2str(self.damping))

            return [axis, limit, dynamics]
        return axis


class Joint(SpatialEntity):
    '''A class representing a joint element'''
    def __init__(self, **kwargs):
        super(Joint, self).__init__(**kwargs)
        self.parent = kwargs.get('parent', '')
        self.child = kwargs.get('child', '')
        self.type = kwargs.get('type', '')
        self.axis = kwargs.get('axis', Axis())

        self.parent_link = None
        self.child_link = None

    def to_xml(self, fmt='sdf'):
        '''returns a joint xml element'''
        super(Joint, self).to_xml(fmt)

        if self.parent_link.parent_joint:
            self.urdf_pose = subtract_poses(self.global_pose,
                                            self.parent_link.parent_joint.global_pose)
        else:
            self.urdf_pose = subtract_poses(self.global_pose, self.parent_link.global_pose)

        joint = ET.Element('joint', {'name': self.name, 'type': self.type})
        pose = self.pose if fmt=='sdf' else self.urdf_pose
        joint.append(pose_to_xml(pose, fmt=fmt))

        parent = ET.SubElement(joint, 'parent')
        child = ET.SubElement(joint, 'child')
        if fmt == 'sdf':
            parent.text = self.parent
            child.text = self.child
            joint.append(self.axis.to_xml(fmt=fmt))
        else:
            parent.set('link', self.parent)
            child.set('link', self.child)
            joint.extend(self.axis.to_xml(fmt=fmt))

        return joint

