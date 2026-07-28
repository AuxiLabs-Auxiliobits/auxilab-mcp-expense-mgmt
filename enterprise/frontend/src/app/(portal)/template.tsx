// Re-mounts on every in-portal navigation, so the routed content fades in
// while the sidebar/top-nav stay put. Opacity-only (no transform) to avoid
// creating a containing block for any fixed/portaled overlays.
export default function PortalTemplate({ children }: { children: React.ReactNode }) {
  return <div className="animate-fade-in">{children}</div>;
}
