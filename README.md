![implementation preview](https://raw.githubusercontent.com/mahaarbo/ARBench/master/UI/icons/github_preview.png)
# Arbench
Annotation for robotics bench. A FreeCAD workbench for annotating frames of interest, exporting these w.r.t. the part frame, and exporting part information.

# Installation instructions
This workbench supports versions of FreeCAD>0.16.

1. [Install FreeCAD](https://www.freecadweb.org/wiki/Installing)
2. If you're not on Ubuntu follow the [workbench installation instructions](https://www.freecadweb.org/wiki/How_to_install_additional_workbenches) or you can do the following on Ubuntu.
3. Custom workbenches are located in `.FreeCAD/Mod/` under your home directory
`cd ~/.FreeCAD/Mod/`
3. Either
   - Clone the repository there
   - symlink the cloned repo in there (`ln -s ./ARBench ~/.FreeCAD/ARBench`)
4. Start the workbench by
   1. Running FreeCAD
   2. Open a STEP file
   3. Open the `ARBench` workbench

# Usage

1. Click a small feature e.g. a circle
2. Press the feature frame creator (cone with a magnifying glass on it icon)
3. Chose type of feature to create
4. Chose feature parameters if relevant and the offset of the frame from the feature.
5. Repeat 4 for each feature you want on each part
6. Click a part and press the export to json button (block->textfile icon)
7. Save json
8. Use the json with whatever you want. E.g. [`arbench_part_publisher`](https://github.com/mahaarbo/arbench_part_publisher)


# Freecad to Gazebo exporter

To generate SDF and URDF model from freecad assembly use python call:

```python
freecad_exporter.export_gazebo_model(freecad_assembly_file, model_destination_folder, config)
```
Note: Only links and joints are generated in the SDF model. To use the model with ros, use the URDF model.

## Config specification
```json
{
    "name": "robot_name",
    "joints_limits": {"upper": 90, "lower": -90, "effort": 10, "velocity": 5},
    "transmission": {
        "type": "transmission_interface/SimpleTransmission",
        "hardware_interface": "hardware_interface/PositionJointInterface"
    },
    "joints_config": {
        "type": "position_controllers/JointGroupPositionController",
        "grouped": true
    },
    "joints_pid": {"p": 20.0, "i": 10.0, "d": 0.0, "i_clamp": 0.0},
    "root_link": "base_link",
    "ros_package": "humanoid_17dof_description",
    "sdf_only": false,
    "export": true
}
```

**sdf_only**: Export only SDF.

**export**: Export mesh files.

## Future plans
* Extend collada exporter to export materials from assemblies.
* Create a FreeCAD workbench to interactively assign joints and export to gazebo.
* Support any valid structures of assemblies.
