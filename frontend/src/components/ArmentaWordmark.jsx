import React from "react";

const LOGO_SRC = "/armenta_logo.png";

export function ArmentaWordmark({ width = 320, className = "", glow = true }) {
  return (
    <img
      src={LOGO_SRC}
      alt="ARMENTA'S MOTORS"
      style={{ width, height: "auto", filter: glow ? "drop-shadow(0 0 28px rgba(220,38,38,0.25))" : undefined }}
      className={`object-contain select-none ${className}`}
      draggable={false}
    />
  );
}
