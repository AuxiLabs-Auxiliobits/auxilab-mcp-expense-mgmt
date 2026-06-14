// REFERENCE SCAFFOLD ONLY — see README.md.
// Standard shadcn/ui class-merge helper (used by ui/ primitives in a real build).

import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
