import React from "react";

/**
 * ARMENTA'S MOTORS — Primary Wordmark (SVG faithful to the identity system).
 * Chrome oval + red car silhouette floating above the ARMENTA'S wordmark,
 * with the red "MOTORS" tagline underneath. Rendered as pure SVG so it
 * scales on every screen without image assets.
 */
export function ArmentaWordmark({ width = 320, className = "" }) {
  return (
    <svg
      viewBox="0 0 640 300"
      width={width}
      className={className}
      role="img"
      aria-label="ARMENTA'S MOTORS"
    >
      <defs>
        <linearGradient id="wm-oval" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#f4f4f5" />
          <stop offset="45%" stopColor="#a1a1aa" />
          <stop offset="100%" stopColor="#3f3f46" />
        </linearGradient>
        <linearGradient id="wm-text" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#f8fafc" />
          <stop offset="50%" stopColor="#d4d4d8" />
          <stop offset="100%" stopColor="#71717a" />
        </linearGradient>
        <linearGradient id="wm-car" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#ef4444" />
          <stop offset="100%" stopColor="#991b1b" />
        </linearGradient>
      </defs>

      {/* Chrome oval outline */}
      <ellipse
        cx="320"
        cy="150"
        rx="300"
        ry="120"
        fill="none"
        stroke="url(#wm-oval)"
        strokeWidth="5"
      />
      <ellipse
        cx="320"
        cy="150"
        rx="290"
        ry="112"
        fill="none"
        stroke="#0a0a0a"
        strokeWidth="1"
      />

      {/* Red sports car silhouette (top curve) */}
      <path
        d="M 155 96
           C 200 68, 260 56, 320 56
           C 380 56, 445 66, 495 96
           C 470 78, 420 74, 375 74
           L 355 62 L 315 58 L 285 74
           C 240 78, 190 84, 155 96 Z"
        fill="url(#wm-car)"
      />
      {/* Motion streaks */}
      <path d="M 435 90 L 500 92" stroke="#ef4444" strokeWidth="3" strokeLinecap="round" opacity="0.75" />
      <path d="M 455 100 L 505 102" stroke="#ef4444" strokeWidth="2" strokeLinecap="round" opacity="0.55" />

      {/* ARMENTA'S main wordmark */}
      <text
        x="320"
        y="182"
        textAnchor="middle"
        fontFamily="'Barlow Condensed', Impact, sans-serif"
        fontWeight="800"
        fontSize="80"
        letterSpacing="2"
        fill="url(#wm-text)"
        stroke="#18181b"
        strokeWidth="1.2"
      >
        ARMENTA'S
      </text>

      {/* MOTORS tagline */}
      <text
        x="320"
        y="232"
        textAnchor="middle"
        fontFamily="'Barlow Condensed', Impact, sans-serif"
        fontWeight="700"
        fontSize="34"
        letterSpacing="14"
        fill="#dc2626"
      >
        MOTORS
      </text>
    </svg>
  );
}
