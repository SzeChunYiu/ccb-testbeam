#!/usr/bin/env python3
"""
patch_gdml_sdetect.py - Add EFFICIENCY=1.0 skin surfaces to CCB sensor volumes.

ROOT CAUSE (Opticks SURFACE_DETECT gap):
  The CCB sensor volumes (Sensor_F1/2_PlusX/MinusX) use CCB_Y11Core material
  (same as the fibre core) with NO detect surface. The only surface in the
  entire geometry is TiO2_Border (REFLECTIVITY only). When photons cross a
  sensor boundary, qbnd::fill_state reads osur=-1 -> no surface ->
  s.optical.y = ems = smatsur_NoSurface. qsim::propagate then routes to
  propagate_at_boundary (Fresnel refraction) instead of propagate_at_surface
  (detect), so SURFACE_DETECT never fires and num_hit stays 0/null.

FIX:
  Add an optical surface with EFFICIENCY=1.0 and attach it as a G4 skin
  surface to each of the 4 sensor logical volumes. On re-ingest this creates
  new boundary entries with detect=1.0, so photons crossing into a sensor
  volume are detected (SURFACE_DETECT hit).
"""
import sys
import xml.etree.ElementTree as ET

def main():
    if len(sys.argv) < 2:
        print("usage: patch_gdml_sdetect.py <origin.gdml>", file=sys.stderr)
        return 1
    gdml_path = sys.argv[1]

    ET.register_namespace('xsi', 'http://www.w3.org/2001/XMLSchema-instance')
    tree = ET.parse(gdml_path)
    root = tree.getroot()

    # 1. Add EFFICIENCY matrix to <define>
    define = root.find('define')
    assert define is not None, "no <define> in GDML"
    ET.SubElement(define, 'matrix', {
        'coldim': '2', 'name': 'EFFICIENCY_CCB_Sensor',
        'values': '1.5e-06 1 2e-06 1 2.5e-06 1 3e-06 1 3.5e-06 1 4e-06 1',
    })

    # 2. Add opticalsurface to <solids>
    solids = root.find('solids')
    assert solids is not None, "no <solids> in GDML"
    os_elem = ET.SubElement(solids, 'opticalsurface', {
        'finish': '0', 'model': '0', 'name': 'CCB_SensorDetect',
        'type': '1', 'value': '0',
    })
    ET.SubElement(os_elem, 'property', {
        'name': 'EFFICIENCY', 'ref': 'EFFICIENCY_CCB_Sensor',
    })

    # 3. Add skinsurfaces to <structure>
    structure = root.find('structure')
    assert structure is not None, "no <structure> in GDML"
    sensor_vols = []
    for vol in structure.findall('volume'):
        name = vol.get('name', '')
        if 'Sensor_F' in name and ('PlusX' in name or 'MinusX' in name):
            sensor_vols.append(name)
    assert len(sensor_vols) == 4, \
        "expected 4 sensor volumes, found %d: %s" % (len(sensor_vols), sensor_vols)
    for sv in sorted(sensor_vols):
        ss = ET.SubElement(structure, 'skinsurface', {
            'name': 'CCB_SensorSkin_%s' % sv, 'surfaceproperty': 'CCB_SensorDetect',
        })
        ET.SubElement(ss, 'volumeref', {'ref': sv})

    tree.write(gdml_path, encoding='UTF-8', xml_declaration=True)
    print("[patch_gdml_sdetect] Patched %s" % gdml_path)
    print("  Skin surfaces on %d sensor volumes:" % len(sensor_vols))
    for sv in sorted(sensor_vols):
        print("    %s" % sv)
    return 0

if __name__ == '__main__':
    sys.exit(main())
