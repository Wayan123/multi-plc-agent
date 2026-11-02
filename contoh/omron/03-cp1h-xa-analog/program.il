; SECTION Analog_Validity
; RUNG 1: Valid AI0: ready, not first scan/error/#8000.
LD A434.04
ANDNOT A315.14
ANDNOT A200.11
AND<>(305) 200 #8000
OUT W0.00

; RUNG 2: Valid AI1: ready, not first scan/error/#8000; reject open circuit.
LD A434.04
ANDNOT A315.14
ANDNOT A200.11
AND<>(305) 201 #8000
ANDNOT A434.01
OUT W0.01

; RUNG 3: Valid AI2: ready, not first scan/error/#8000.
LD A434.04
ANDNOT A315.14
ANDNOT A200.11
AND<>(305) 202 #8000
OUT W0.02

; RUNG 4: Valid AI3: ready, not first scan/error/#8000; reject open circuit.
LD A434.04
ANDNOT A315.14
ANDNOT A200.11
AND<>(305) 203 #8000
ANDNOT A434.03
OUT W0.03

; RUNG 5: All AI channels must be valid to enable both AO channels; a fault on either channel drives both low.
LD W0.00
AND W0.01
AND W0.02
AND W0.03
OUT W0.04

; SECTION HMI_Input_Publication
; RUNG 1: Clear the AI0 published value every scan; invalid data does not remain as a valid value.
LD P_On
MOV(021) &0 D100

; RUNG 2: Copy AI0 only when validity is ON.
LD W0.00
MOV(021) 200 D100

; RUNG 3: Clear the AI1 published value every scan; invalid data does not remain as a valid value.
LD P_On
MOV(021) &0 D101

; RUNG 4: Copy AI1 only when validity is ON.
LD W0.01
MOV(021) 201 D101

; RUNG 5: Clear the AI2 published value every scan; invalid data does not remain as a valid value.
LD P_On
MOV(021) &0 D102

; RUNG 6: Copy AI2 only when validity is ON.
LD W0.02
MOV(021) 202 D102

; RUNG 7: Clear the AI3 published value every scan; invalid data does not remain as a valid value.
LD P_On
MOV(021) &0 D103

; RUNG 8: Copy AI3 only when validity is ON.
LD W0.03
MOV(021) 203 D103

; SECTION AO_Command_Arbitration
; RUNG 1: Default scratch AO0=0 every scan; startup, fault, or a negative command selects low.
LD P_On
MOV(021) &0 D210

; RUNG 2: Signed AO0 command within nominal 0..6000 is passed through.
LD W0.04
AND>=S(327) D200 &0
AND<=S(317) D200 &6000
MOV(021) D200 D210

; RUNG 3: AO0 commands above 6000 are saturated; signed comparison prevents -1 from becoming a positive overrange.
LD W0.04
AND>S(322) D200 &6000
MOV(021) &6000 D210

; RUNG 4: Default scratch AO1=0 every scan; startup, fault, or a negative command selects low.
LD P_On
MOV(021) &0 D211

; RUNG 5: Signed AO1 command within nominal 0..6000 is passed through.
LD W0.04
AND>=S(327) D201 &0
AND<=S(317) D201 &6000
MOV(021) D201 D211

; RUNG 6: AO1 commands above 6000 are saturated; signed comparison prevents -1 from becoming a positive overrange.
LD W0.04
AND>S(322) D201 &6000
MOV(021) &6000 D211

; SECTION Final_AO_Writers
; RUNG 1: Sole CIO210 writer; raw 0 means 0 V.
LD P_On
MOV(021) D210 210

; RUNG 2: Sole CIO211 writer; raw 0 means 4 mA in the normal configuration.
LD P_On
MOV(021) D211 211

