#!/usr/bin/env python3
"""
patch_gdml_trigger_volumes.py - Add T1/T2 trigger scintillator volumes to HIBEAM GDML

Phase 2 of #1045: Add trigger scintillator volumes to the HIBEAM geometry.

T1: A-arm trigger scintillator (PSci, 1 cm thick, 71.5° from beam)
T2: B-arm trigger scintillator (PSci, 1 cm thick, -38° from beam)

Material: PSci (polystyrene, ρ=1.032 g/cm³, C/H composition) - already in GDML
"""

import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom

def prettify(elem):
    """Return a pretty-printed XML string."""
    rough_string = ET.tostring(elem, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent='  ')

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <gdml_file>", file=sys.stderr)
        return 1
    
    gdml_path = sys.argv[1]
    
    # Register namespaces
    ET.register_namespace('xsi', 'http://www.w3.org/2001/XMLSchema-instance')
    
    tree = ET.parse(gdml_path)
    root = tree.getroot()
    
    # Find the define and solids sections
    define = root.find('define')
    solids = root.find('solids')
    structure = root.find('structure')
    
    if define is None or solids is None or structure is None:
        print("ERROR: Missing required sections in GDML", file=sys.stderr)
        return 1
    
    # === T1 (A-arm) Trigger Scintillator ===
    # Position: 71.5° from beam, upstream of HRD
    # Size: 10 cm x 10 cm x 1 cm (L x W x T)
    # Position along beam: ~30 cm upstream of HRD first layer
    
    # Add positions for T1
    # T1 is placed at 71.5°, 30 cm upstream of HRD (z = -30 cm in lab frame)
    # Rotation: 71.5° around Y axis
    t1_position = ET.SubElement(define, 'position', {
        'name': 'T1_trigger_pos',
        'x': '10.5',  # offset from beam axis for 71.5°
        'y': '0',
        'z': '-30',
        'unit': 'cm'
    })
    
    t1_rotation = ET.SubElement(define, 'rotation', {
        'name': 'T1_trigger_rot',
        'x': '0',
        'y': '71.5',
        'z': '0',
        'unit': 'deg'
    })
    
    # === T2 (B-arm) Trigger Scintillator ===
    # Position: -38° from beam, upstream of HRD
    # Size: 15 cm x 15 cm x 1 cm (L x W x T)
    # Position along beam: ~30 cm upstream of HRD first layer
    
    # Add positions for T2
    # T2 is placed at -38°, 30 cm upstream of HRD
    # Rotation: -38° around Y axis
    t2_position = ET.SubElement(define, 'position', {
        'name': 'T2_trigger_pos',
        'x': '-12.0',  # offset from beam axis for -38°
        'y': '0',
        'z': '-30',
        'unit': 'cm'
    })
    
    t2_rotation = ET.SubElement(define, 'rotation', {
        'name': 'T2_trigger_rot',
        'x': '0',
        'y': '-38',
        'z': '0',
        'unit': 'deg'
    })
    
    # === Add T1 volume (box shape) ===
    t1_box = ET.SubElement(solids, 'box', {
        'name': 'T1_trigger_box',
        'x': '10',  # 10 cm length
        'y': '10',  # 10 cm width
        'z': '1',   # 1 cm thickness
        'lunit': 'cm'
    })
    
    # === Add T2 volume (box shape) ===
    t2_box = ET.SubElement(solids, 'box', {
        'name': 'T2_trigger_box',
        'x': '15',  # 15 cm length
        'y': '15',  # 15 cm width
        'z': '1',   # 1 cm thickness
        'lunit': 'cm'
    })
    
    # Find the world volume
    world_vol = None
    for vol in structure.findall('volume'):
        if vol.get('name') == 'MOTHER':
            world_vol = vol
            break
    
    if world_vol is None:
        print("ERROR: Could not find MOTHER (world) volume", file=sys.stderr)
        return 1
    
    # === Create T1 logical volume ===
    t1_log = ET.Element('volume', {'name': 'T1_trigger_log'})
    ET.SubElement(t1_log, 'materialref', {'ref': 'PSci'})
    ET.SubElement(t1_log, 'solidref', {'ref': 'T1_trigger_box'})
    
    # Insert T1 logical volume before world volume
    structure_idx = list(structure).index(world_vol)
    structure.insert(structure_idx, t1_log)
    
    # === Create T2 logical volume ===
    t2_log = ET.Element('volume', {'name': 'T2_trigger_log'})
    ET.SubElement(t2_log, 'materialref', {'ref': 'PSci'})
    ET.SubElement(t2_log, 'solidref', {'ref': 'T2_trigger_box'})
    
    # Insert T2 logical volume before world volume
    structure.insert(structure_idx, t2_log)
    
    # === Find the experimental hall physical volume ===
    # Add T1/T2 as daughters of MOTHER (world) volume
    # Find the structure section after volumes
    for elem in structure:
        if elem.tag == 'volume' and elem.get('name') == 'MOTHER':
            # Add T1 physical volume
            t1_phys = ET.SubElement(elem, 'physvol', {'name': 'T1_trigger_phys'})
            t1_volref = ET.SubElement(t1_phys, 'volumeref', {'ref': 'T1_trigger_log'})
            t1_posref = ET.SubElement(t1_phys, 'positionref', {'ref': 'T1_trigger_pos'})
            t1_rotref = ET.SubElement(t1_phys, 'rotationref', {'ref': 'T1_trigger_rot'})
            
            # Add T2 physical volume
            t2_phys = ET.SubElement(elem, 'physvol', {'name': 'T2_trigger_phys'})
            t2_volref = ET.SubElement(t2_phys, 'volumeref', {'ref': 'T2_trigger_log'})
            t2_posref = ET.SubElement(t2_phys, 'positionref', {'ref': 'T2_trigger_pos'})
            t2_rotref = ET.SubElement(t2_phys, 'rotationref', {'ref': 'T2_trigger_rot'})
            break
    
    # Write the modified GDML
    tree.write(gdml_path, encoding='UTF-8', xml_declaration=True)
    
    print(f"[patch_gdml_trigger_volumes] Patched {gdml_path}")
    print("  Added T1 trigger scintillator (A-arm, 71.5°, 10x10x1 cm)")
    print("  Added T2 trigger scintillator (B-arm, -38°, 15x15x1 cm)")
    print("  Material: PSci (polystyrene)")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
