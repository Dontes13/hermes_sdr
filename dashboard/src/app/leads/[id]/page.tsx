"use client";

import { use } from "react";
import { LeadDetailView } from "@/components/leads/LeadDetailView";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function LeadDetailPage({ params }: PageProps) {
  const { id } = use(params);
  return <LeadDetailView leadId={id} />;
}
