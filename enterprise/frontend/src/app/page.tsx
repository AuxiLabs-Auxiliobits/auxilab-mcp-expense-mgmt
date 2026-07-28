import { redirect } from "next/navigation";

export default function Home() {
  // The root always lands on the login page (the app's entry point), even for an
  // already-authenticated user — they can navigate into their portal from there.
  redirect("/login");
}
