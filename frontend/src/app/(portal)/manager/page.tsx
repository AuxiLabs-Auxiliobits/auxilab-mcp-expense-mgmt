import type { Metadata } from "next";
import { ReviewQueue } from "@/features/manager/review-queue";

export const metadata: Metadata = { title: "Manager Dashboard" };

export default function ManagerPage() {
  return <ReviewQueue />;
}
