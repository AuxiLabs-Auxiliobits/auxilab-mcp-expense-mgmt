"use client";

import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";

/**
 * A receipt the employee uploaded on the "My Receipts" page but hasn't yet attached
 * to a line item ("Unassigned"). These live only in client memory for the session —
 * the bytes never hit the backend until they're attached to a line item (via the
 * line-item dialog's existing `uploadReceipt` path). The store is what lets the two
 * screens share the same pool: upload here, pick there.
 */
export type UploadedReceipt = {
  id: string;
  fileName: string;
  fileType: string;
  sizeBytes: number;
  file: File;
};

interface ReceiptUploadsContextValue {
  uploads: UploadedReceipt[];
  /** Add picked files to the unassigned pool; returns the rows created. */
  addUploads: (files: File[]) => UploadedReceipt[];
  /** Remove one upload (used by the My Receipts delete, and once it's attached). */
  removeUpload: (id: string) => void;
}

const ReceiptUploadsContext = createContext<ReceiptUploadsContextValue | null>(null);

export function ReceiptUploadsProvider({ children }: { children: React.ReactNode }) {
  const [uploads, setUploads] = useState<UploadedReceipt[]>([]);
  const idRef = useRef(0);

  const addUploads = useCallback((files: File[]) => {
    const rows: UploadedReceipt[] = files.map((f) => ({
      id: `upload-${idRef.current++}`,
      fileName: f.name,
      fileType: f.type || "application/octet-stream",
      sizeBytes: f.size,
      file: f,
    }));
    setUploads((prev) => [...rows, ...prev]);
    return rows;
  }, []);

  const removeUpload = useCallback((id: string) => {
    setUploads((prev) => prev.filter((u) => u.id !== id));
  }, []);

  const value = useMemo(
    () => ({ uploads, addUploads, removeUpload }),
    [uploads, addUploads, removeUpload],
  );

  return (
    <ReceiptUploadsContext.Provider value={value}>{children}</ReceiptUploadsContext.Provider>
  );
}

export function useReceiptUploads() {
  const ctx = useContext(ReceiptUploadsContext);
  if (!ctx) {
    throw new Error("useReceiptUploads must be used within a ReceiptUploadsProvider");
  }
  return ctx;
}
