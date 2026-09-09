"use client";

import { Shell } from "@/components/shell";
import { SkeletonRows } from "@/components/ui";
import { AppProvider, useApp } from "@/lib/store";

function Gate({ children }: { children: React.ReactNode }) {
  const { loading } = useApp();
  if (loading) {
    return (
      <div className="mx-auto max-w-3xl pt-24">
        <SkeletonRows rows={8} />
      </div>
    );
  }
  return <Shell>{children}</Shell>;
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppProvider>
      <Gate>{children}</Gate>
    </AppProvider>
  );
}
