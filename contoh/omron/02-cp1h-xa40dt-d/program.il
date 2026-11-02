; SECTION Motor_Prestart_Control
; RUNG 1: Request seal-in; Stop, permissive loss, and first cycle always override Start and self-hold.
LD 0.00
AND W0.01
OR W0.00
AND 0.01
AND 1.00
ANDNOT A200.11
OUT W0.00

; RUNG 2: Arm only after Start is released while ready; clear while the request is active.
LDNOT 0.00
OR W0.01
AND 0.01
AND 1.00
ANDNOT W0.00
ANDNOT A200.11
OUT W0.01

; RUNG 3: TIM uses BCD preset 0030 x 0.1 s = 3 s; loss of the request resets the timer.
LD W0.00
TIM 0000 #0030

; RUNG 4: Horn only during prestart; one writer for the physical horn output.
LD W0.00
ANDNOT T0000
OUT 100.00

; RUNG 5: Motor only after the timer completes; one writer for the physical motor output.
LD W0.00
AND T0000
OUT 101.00

