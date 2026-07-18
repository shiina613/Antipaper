import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import "./globals.css";
import Landing from "./routes/Landing";
import Workspace from "./routes/Workspace";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/app" element={<Workspace />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
