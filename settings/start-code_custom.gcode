M862.3 P "[printer_model]" ; printer model check
M862.1 P[nozzle_diameter] ; nozzle diameter check
M115 U3.11.0 ; tell printer latest fw version
G90 ; use absolute coordinates
M83 ; extruder relative mode

M104 S{if first_layer_temperature[0]<220}110{else}120{endif} ; preheat extruder to lower temp
M140 S[first_layer_bed_temperature] ; set bed temp
M190 S[first_layer_bed_temperature] ; wait for bed temp

; ready sound
M300 S440 P200
M300 S660 P250
; end ready sou

; start ramp up to preheat temp before bed level
M104 S{if first_layer_temperature[0]<220}180{else}200{endif} ; preheat extruder to lower temp

G28 W ; home all without mesh bed level
G80 ; mesh bed leveling

G1 Z40 F750 ; lift nozzle before heating it to final temp
M104 S[first_layer_temperature] ; set extruder temp
M109 S[first_layer_temperature] ; wait for extruder temp

; startup sound
M300 S440 P200
M300 S660 P250
M300 S880 P300
; end startup sound

{if filament_settings_id[initial_tool]=~/.*Prusament PA11.*/}
G1 Z0.3 F720
G1 Y-3 F1000 ; go outside print area
G92 E0
G1 X60 E9 F1000 ; intro line
G1 X100 E9 F1000 ; intro line
{else}
G1 Z0.2 F720
G1 Y-3 F1000 ; go outside print area
G92 E0
G1 X60 E9 F1000 ; intro line
G1 X100 E12.5 F1000 ; intro line
{endif}
G92 E0
M221 S{if layer_height<0.075}100{else}95{endif}

; Don't change E values below. Excessive value can damage the printer.
{if print_settings_id=~/.*(DETAIL @MK3|QUALITY @MK3).*/}M907 E430 ; set extruder motor current{endif}
{if print_settings_id=~/.*(SPEED @MK3|DRAFT @MK3).*/}M907 E538 ; set extruder motor current{endif}
