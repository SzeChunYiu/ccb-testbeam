Instructions

1.  Get hibeam_g4 from https://github.com/HIBEAM-NNBAR/hibeam_g4 and follow installation instructions.
2.  Extract archive to hibeam_g4 build folder.
3.  Run hibeam_g4: ./hibeam_g4 -c krakow.config -m run_krakow.mac output_krakow.root
3.a The test setup geometry is in krakow_109_8-38deg_4-71deg.root. To create a new geometry file hibeam_g4_geobuilder (https://github.com/HIBEAM-NNBAR/hibeam_g4_geobuilder) can be used with the krakow.geoconf file.
4.  Convert output data with hibeam_g4_analysis: https://github.com/HIBEAM-NNBAR/hibeam_g4_analysis
