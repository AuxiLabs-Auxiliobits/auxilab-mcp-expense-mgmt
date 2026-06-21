import { cn } from "@/lib/utils";

/** Standard padded, max-width page canvas used by the dashboard-style views. */
export function PageContainer({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "mx-auto w-full max-w-container-max p-gutter md:p-margin-page",
        className,
      )}
    >
      {children}
    </div>
  );
}
