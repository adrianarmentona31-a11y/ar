import React from "react";

const HEX_SRC = "/armenta_hex.png";

/**
 * ARMENTA'S MOTORS — official brand mark (hex-A monogram) as raster asset.
 * Preserves the photo of the physical medallion; renders on any dark background
 * thanks to the transparent ellipse mask baked into the PNG.
 */
export function BrandMark({ size = 40, glow = false, className = "", title = "ARMENTA'S MOTORS" }) {
  const style = {
    width: size,
    height: size,
    filter: glow ? "drop-shadow(0 0 18px rgba(220, 38, 38, 0.55))" : undefined,
  };
  return (
    <img
      src={HEX_SRC}
      alt={title}
      style={style}
      className={`object-contain select-none ${className}`}
      draggable={false}
    />
  );
}
