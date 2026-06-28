import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";

// Canonical Next.js 15 + ESLint 9 flat-config bridge. eslint-config-next ships legacy
// (.eslintrc-style) shareable configs, so FlatCompat adapts them to flat config — importing
// the subpaths directly fails under ESLint 9 ("not iterable" / ERR_MODULE_NOT_FOUND).
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const compat = new FlatCompat({ baseDirectory: __dirname });

const eslintConfig = [
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  { ignores: [".next/**", "out/**", "build/**", "next-env.d.ts"] },
];

export default eslintConfig;
