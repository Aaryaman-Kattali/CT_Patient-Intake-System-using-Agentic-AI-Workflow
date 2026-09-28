import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { StaffPage } from "./StaffPage";
import "./styles.css";

// Two pages: the patient's form, and the staff view (demo) at /staff/<intake id>.
// The staff page is reached only by typing its address; the form never links to it.
const staff = /^\/staff\/([0-9a-f-]{36})\/?$/i.exec(window.location.pathname);

createRoot(document.getElementById("root")!).render(
  <StrictMode>{staff?.[1] ? <StaffPage intakeId={staff[1]} /> : <App />}</StrictMode>,
);
