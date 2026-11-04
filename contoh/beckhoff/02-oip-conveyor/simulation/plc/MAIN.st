PROGRAM MAIN
VAR_INPUT
    StartPB : BOOL;
    StopNC : BOOL := TRUE;
    EStopHealthy : BOOL := TRUE;
    PartSensor : BOOL;
    CountReset : BOOL;
    BeltRunning : BOOL;
    Spawned : DINT;
    Delivered : INT;
END_VAR
VAR_OUTPUT
    Horn : BOOL;
    Motor : BOOL;
    BatchLamp : BOOL;
END_VAR
VAR
    RunReq : BOOL;
    PartPulse : BOOL;
    LastPartSensor : BOOL;
    StartDelay : TON;
    BatchCounter : CTU;
END_VAR

(* Contract-equivalent IEC implementation; native TwinCAT LD is a separate artifact. *)
RunReq := (StartPB OR RunReq) AND StopNC AND EStopHealthy AND NOT BatchCounter.Q;
StartDelay(IN := RunReq, PT := T#3S);
Horn := RunReq AND NOT StartDelay.Q;
Motor := RunReq AND StartDelay.Q;
PartPulse := PartSensor AND NOT LastPartSensor;
LastPartSensor := PartSensor;
BatchCounter(CU := Motor AND PartPulse, R := CountReset, PV := 10);
BatchLamp := BatchCounter.Q;
END_PROGRAM
