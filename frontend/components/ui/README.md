# `components/ui/` — shadcn/ui primitives (placeholder)

**REFERENCE SCAFFOLD ONLY.**

In a real build, this directory holds [shadcn/ui](https://ui.shadcn.com) primitives
(Button, Card, Dialog, Table, Form, Select, Badge, …) generated on demand with:

```bash
npx shadcn@latest init
npx shadcn@latest add button card dialog table form select badge
```

shadcn/ui copies the component source into this folder (you own it) rather than
installing a package. The components are styled with the Tailwind CSS-variable
theme tokens defined in `app/globals.css` and `tailwind.config.ts`.

Nothing is generated here in the reference scaffold to avoid shipping unused code.
The stub components (`SheetGrid`, `KpiTiles`, `SpendChart`, `RoleNav`) use plain
Tailwind utility classes in place of these primitives.
