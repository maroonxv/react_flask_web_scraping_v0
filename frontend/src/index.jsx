import React from "react";
import { createRoot } from "react-dom/client";
import StartStopPanel from "./features/test_start_stop/StartStopPanel";

const root = createRoot(document.getElementById("root"));
root.render(<StartStopPanel />);
