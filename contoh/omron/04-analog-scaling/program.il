; SECTION Signed32_Constants
; RUNG 1: Fixed signed32 divisor; MOVL writes both low and high words instead of reading an unknown high word from the next address.
LD P_On
MOVL(498) &6000 D170

; RUNG 2: Signed32 divisor/offset=1000; the high word is set to 0 every scan.
LD P_On
MOVL(498) &1000 D172

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

; SECTION Math_Defaults_Each_Scan
; RUNG 1: Default input clamp to 0 every scan.
LD P_On
MOV(021) &0 D104

; RUNG 2: Clear the input product word pair; invalid data leaves no stale published value or quotient.
LD P_On
MOVL(498) &0 D110

; RUNG 3: Clear the input quotient word pair; invalid data leaves no stale published value or quotient.
LD P_On
MOVL(498) &0 D120

; RUNG 4: Clear the input remainder word pair; invalid data leaves no stale published value or quotient.
LD P_On
MOVL(498) &0 D122

; RUNG 5: Clear the engineering value word pair; invalid data leaves no stale published value or quotient.
LD P_On
MOVL(498) &0 D130

; RUNG 6: Clear the output product word pair; invalid data leaves no stale published value or quotient.
LD P_On
MOVL(498) &0 D150

; RUNG 7: Clear the output quotient word pair; invalid data leaves no stale published value or quotient.
LD P_On
MOVL(498) &0 D160

; RUNG 8: Clear the output remainder word pair; invalid data leaves no stale published value or quotient.
LD P_On
MOVL(498) &0 D162

; SECTION Signed32_Input_Scaling
; RUNG 1: Only valid AI0 may enter the scaling path.
LD W0.00
MOV(021) D100 D104

; RUNG 2: Clamp negative extended signed input before multiplication.
LD W0.00
AND<S(312) D100 &0
MOV(021) &0 D104

; RUNG 3: Clamp signed input above nominal 6000 before multiplication.
LD W0.00
AND>S(322) D100 &6000
MOV(021) &6000 D104

; RUNG 4: Signed16 x signed16 -> signed32; the maximum product 12000000 exceeds 16 bits.
LD W0.00
*(420) D104 &2000 D110

; RUNG 5: Divide signed32 by the divisor pair 6000; reserve D120..123 for quotient and remainder.
LD W0.00
/L(431) D110 D170 D120

; RUNG 6: Quotient 0..2000 minus signed32 offset 1000 -> engineering -1000..1000.
LD W0.00
-L(411) D120 D172 D130

; RUNG 7: Engineering value is valid only when AI0 is valid; default zero is not a valid measurement.
LD W0.00
OUT W0.05

; SECTION Output_Scaling_And_Final_Writer
; RUNG 1: Command defaults to 0; the fault gate and negative commands select low.
LD P_On
MOV(021) &0 D140

; RUNG 2: Command 0..1000 passes after signed clamping when all AI channels are valid.
LD W0.04
AND>=S(327) D200 &0
AND<=S(317) D200 &1000
MOV(021) D200 D140

; RUNG 3: Commands above 1000 are saturated before multiplication.
LD W0.04
AND>S(322) D200 &1000
MOV(021) &1000 D140

; RUNG 4: Signed16 x signed16 -> signed32; maximum 6000000, not 16-bit.
LD W0.04
*(420) D140 &6000 D150

; RUNG 5: Signed32 division uses D172..173=1000; all of D160..163 is allocated.
LD W0.04
/L(431) D150 D172 D160

; RUNG 6: Sole AO0 writer; quotient low 0..6000, default 0 when invalid.
LD P_On
MOV(021) D160 210

; RUNG 7: Sole AO1 writer; raw 0 means 4 mA, not 0 mA.
LD P_On
MOV(021) D160 211

