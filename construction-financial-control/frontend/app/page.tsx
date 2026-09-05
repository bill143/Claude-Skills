"use client";

import { useEffect } from "react";
import { getToken } from "@/lib/api";

export default function Index() {
  useEffect(() => {
    window.location.href = getToken() ? "/dashboard" : "/login";
  }, []);
  return null;
}
