import React, { useEffect, useState } from "react";
import { api } from "../lib/api";

const cache = new Map();

export function SecureImg({ fileId, alt = "", className = "" }) {
  const [src, setSrc] = useState(cache.get(fileId) || "");
  useEffect(() => {
    if (cache.get(fileId)) return;
    let alive = true;
    api.get(`/files/${fileId}/view-token`).then(({ data }) => {
      const url = `${process.env.REACT_APP_BACKEND_URL}/api/files/${fileId}/download?auth=${encodeURIComponent(data.token)}`;
      cache.set(fileId, url);
      if (alive) setSrc(url);
    }).catch(() => {});
    return () => { alive = false; };
  }, [fileId]);
  if (!src) return <div className={`${className} bg-[#111] animate-pulse`} />;
  return <img src={src} alt={alt} className={className} />;
}
