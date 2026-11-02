; SECTION Traffic_Light
; RUNG 1: The first scan initializes the initial all-red stage, ignoring the retained D0 value.
LD A200.11
MOV #0000 D0

; RUNG 2: Stage 0 timer: initial all-red, 2 seconds; BCD preset in 0.1-second units.
LD= D0 #0000
TIM 0000 #0020

; RUNG 3: Stage 1 timer: north-south green, 10 seconds; BCD preset in 0.1-second units.
LD= D0 #0001
TIM 0001 #0100

; RUNG 4: Stage 2 timer: north-south yellow, 3 seconds; BCD preset in 0.1-second units.
LD= D0 #0002
TIM 0002 #0030

; RUNG 5: Stage 3 timer: all-red transition, 2 seconds; BCD preset in 0.1-second units.
LD= D0 #0003
TIM 0003 #0020

; RUNG 6: Stage 4 timer: east-west green, 10 seconds; BCD preset in 0.1-second units.
LD= D0 #0004
TIM 0004 #0100

; RUNG 7: Stage 5 timer: east-west yellow, 3 seconds; BCD preset in 0.1-second units.
LD= D0 #0005
TIM 0005 #0030

; RUNG 8: Stage 6 timer: pedestrian transition, 2 seconds; BCD preset in 0.1-second units.
LD= D0 #0006
TIM 0006 #0020

; RUNG 9: Stage 7 timer: pedestrian green, 5 seconds; BCD preset in 0.1-second units.
LD= D0 #0007
TIM 0007 #0050

; RUNG 10: Stage 8 timer: all-red after pedestrian stage, 2 seconds; BCD preset in 0.1-second units.
LD= D0 #0008
TIM 0008 #0020

; RUNG 11: After the stage 0 timer completes, advance to stage 1.
LD= D0 #0000
AND T0000
MOV #0001 D0

; RUNG 12: After the stage 1 timer completes, advance to stage 2.
LD= D0 #0001
AND T0001
MOV #0002 D0

; RUNG 13: After the stage 2 timer completes, advance to stage 3.
LD= D0 #0002
AND T0002
MOV #0003 D0

; RUNG 14: After the stage 3 timer completes, advance to stage 4.
LD= D0 #0003
AND T0003
MOV #0004 D0

; RUNG 15: After the stage 4 timer completes, advance to stage 5.
LD= D0 #0004
AND T0004
MOV #0005 D0

; RUNG 16: After the stage 5 timer completes, advance to stage 6.
LD= D0 #0005
AND T0005
MOV #0006 D0

; RUNG 17: After the stage 6 timer completes, advance to stage 7.
LD= D0 #0006
AND T0006
MOV #0007 D0

; RUNG 18: After the stage 7 timer completes, advance to stage 8.
LD= D0 #0007
AND T0007
MOV #0008 D0

; RUNG 19: After the stage 8 timer completes, advance to stage 1.
LD= D0 #0008
AND T0008
MOV #0001 D0

; RUNG 20: North red output.
LD<> D0 #0001
AND<> D0 #0002
OUT 100.00

; RUNG 21: South red output.
LD<> D0 #0001
AND<> D0 #0002
OUT 100.03

; RUNG 22: North yellow output.
LD= D0 #0002
OUT 100.01

; RUNG 23: South yellow output.
LD= D0 #0002
OUT 100.04

; RUNG 24: North green output.
LD= D0 #0001
OUT 100.02

; RUNG 25: South green output.
LD= D0 #0001
OUT 100.05

; RUNG 26: East red output.
LD<> D0 #0004
AND<> D0 #0005
OUT 100.06

; RUNG 27: West red output.
LD<> D0 #0004
AND<> D0 #0005
OUT 101.01

; RUNG 28: East yellow output.
LD= D0 #0005
OUT 100.07

; RUNG 29: West yellow output.
LD= D0 #0005
OUT 101.02

; RUNG 30: East green output.
LD= D0 #0004
OUT 101.00

; RUNG 31: West green output.
LD= D0 #0004
OUT 101.03

; RUNG 32: Pedestrian red output.
LD<> D0 #0007
OUT 101.04

; RUNG 33: Pedestrian green output.
LD= D0 #0007
OUT 101.05

