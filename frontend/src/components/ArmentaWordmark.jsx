import React from "react";

const WORDMARK_SRC = "/armenta_wordmark.png";

/**
 * ARMENTA'S MOTORS — official primary logo (chrome oval + red car silhouette
 * + ARMENTA'S / MOTORS wordmark). Renders the raster asset exactly as provided
 * in the brand identity system.
 */
export function ArmentaWordmark({ width = 320, className = "" }) {
  return (
    <img
      src={WORDMARK_SRC}
      alt="ARMENTA'S MOTORS"
      style={{ width, height: "auto" }}
      className={`object-contain select-none ${className}`}
      draggable={false}
    />
  );
}
