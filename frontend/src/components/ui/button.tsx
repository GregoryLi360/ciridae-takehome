import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 font-mono text-sm uppercase tracking-wider transition-opacity disabled:pointer-events-none disabled:opacity-30 cursor-pointer",
  {
    variants: {
      variant: {
        default: "text-foreground hover:opacity-60",
        outline:
          "border border-foreground text-foreground hover:bg-foreground hover:text-background",
        ghost: "text-muted-foreground hover:text-foreground hover:opacity-60",
      },
      size: {
        default: "py-2",
        sm: "text-xs py-1",
        lg: "text-base py-3",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return (
      <button
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
