import React from "react";

/**
 * ARMENTA'S MOTORS — Brand Mark (Hex-A diminutive icon)
 * Vector faithful to the identity system: red hex outline, obsidian fill,
 * chrome silver monogram A with red inner slot.
 */
export function BrandMark({ size = 40, glow = false, className = "", title = "ARMENTA'S MOTORS" }) {
  const glowStyle = glow
    ? { filter: "drop-shadow(0 0 14px rgba(220, 38, 38, 0.45))" }
    : undefined;
  return (
    <svg
      viewBox="0 0 100 100"
      width={size}
      height={size}
      className={className}
      style={glowStyle}
      role="img"
      aria-label={title}
    >
      <defs>
        <linearGradient id="am-hex-fill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#1a1a1a" />
          <stop offset="55%" stopColor="#0d0d0d" />
          <stop offset="100%" stopColor="#050505" />
        </linearGradient>
        <linearGradient id="am-a-fill" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0%" stopColor="#f4f4f5" />
          <stop offset="50%" stopColor="#d4d4d8" />
          <stop offset="100%" stopColor="#a1a1aa" />
        </linearGradient>
      </defs>

      {/* Outer red rim */}
      <polygon
        points="50,3 92,26 92,74 50,97 8,74 8,26"
        fill="#dc2626"
      />
      {/* Inner obsidian body */}
      <polygon
        points="50,10 86,29 86,71 50,90 14,71 14,29"
        fill="url(#am-hex-fill)"
      />
      {/* Chrome A monogram */}
      <path
        d="M50 25 L74 74 L64 74 L58 62 L42 62 L36 74 L26 74 Z M46 54 L54 54 L50 42 Z"
        fill="url(#am-a-fill)"
      />
      {/* Red highlight slot in A */}
      <path
        d="M46 54 L54 54 L50 42 Z"
        fill="#dc2626"
      />
    </svg>
  );
}

/**
 * Wordmark used inline in headers ("ARMENTA OS" with red OS accent).
 * The primary company wordmark ("ARMENTA'S MOTORS") is rendered separately
 * as small caps typography beneath the mark on the Login screen.
 */
export function BrandWordmark({ className = "" }) {
  return (
    <span
      className={`font-display uppercase font-extrabold tracking-tight ${className}`}
    >
      ARMENTA <span className="text-[#dc2626]">OS</span>
    </span>
  );
}
