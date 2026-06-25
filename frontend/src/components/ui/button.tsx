import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
import { Spinner } from "@/components/ui/spinner";

const buttonVariants = cva(
  "inline-flex select-none items-center justify-center gap-2 whitespace-nowrap rounded-lg text-body-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 [&_.material-symbols-outlined]:text-[18px]",
  {
    variants: {
      variant: {
        default: "bg-primary text-on-primary shadow-xs hover:bg-on-primary-fixed-variant",
        destructive: "bg-error text-on-error shadow-xs hover:bg-error/90",
        outline:
          "border border-outline-variant bg-surface-container-lowest text-on-surface hover:border-outline hover:bg-surface-container-low",
        secondary: "bg-secondary text-on-secondary shadow-xs hover:bg-secondary/90",
        ghost: "text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface",
        link: "text-secondary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4",
        sm: "h-8 px-3",
        lg: "h-11 px-6 text-body-md",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  /** Show an inline spinner and disable the button while an action is in flight. */
  loading?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, loading = false, disabled, children, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    // `asChild` forwards to a single child via Slot, so we can't inject a sibling spinner;
    // the spinner is only added for plain buttons (the common case for async actions).
    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size, className }))}
        disabled={disabled || (loading && !asChild)}
        {...props}
      >
        {!asChild && loading && <Spinner size="sm" className="text-current" />}
        {children}
      </Comp>
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
