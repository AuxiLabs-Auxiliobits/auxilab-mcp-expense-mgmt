import { PageSpinner } from "@/components/ui/spinner";

// Top-level navigation fallback (e.g. the root redirect resolving to a portal/login).
export default function RootLoading() {
  return <PageSpinner className="min-h-screen" />;
}
