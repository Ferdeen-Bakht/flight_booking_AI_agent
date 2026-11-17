import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import { AuthProvider } from "./auth.jsx";
import { StoreProvider } from "./store.jsx";
import ErrorBoundary from "./ErrorBoundary.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <ErrorBoundary>
    <AuthProvider>
      <StoreProvider>
        <App />
      </StoreProvider>
    </AuthProvider>
  </ErrorBoundary>
);
