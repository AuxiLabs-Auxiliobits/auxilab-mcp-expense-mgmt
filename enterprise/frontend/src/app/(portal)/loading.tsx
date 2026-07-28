import { PageSpinner } from "@/components/ui/spinner";

// Shown in the content area (inside the portal shell) while a portal page and its
// data load — gives immediate feedback on navigation between portal routes.
export default function PortalLoading() {
  return <PageSpinner className="min-h-[60vh]" label="Loading…" />;
}
