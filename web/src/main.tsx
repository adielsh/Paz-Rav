import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import AuthGate from "./AuthGate";
import { ThemeProvider } from "./theme-context";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider>
      <AuthGate>{(user) => <App user={user} />}</AuthGate>
    </ThemeProvider>
  </React.StrictMode>,
);
