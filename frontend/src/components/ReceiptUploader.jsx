import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { FiUploadCloud, FiImage, FiCheck, FiLoader, FiDollarSign, FiCalendar, FiTag, FiMapPin, FiSend } from 'react-icons/fi';
import { uploadReceipt, submitExpense } from '../api/client';
import { useAuth } from '../context/AuthContext';
import ConfirmModal from './ConfirmModal';



export default function ReceiptUploader({ onUploadComplete }) {
  const { user } = useAuth();
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [extracted, setExtracted] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState(null);
  const [showSubmitConfirm, setShowSubmitConfirm] = useState(false);

  const onDrop = useCallback(async (acceptedFiles) => {
    if (acceptedFiles.length === 0) return;
    const f = acceptedFiles[0];
    setFile(f);
    setExtracted(null);
    setSubmitted(false);
    setError(null);

    // Create preview
    if (f.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = () => setPreview(reader.result);
      reader.readAsDataURL(f);
    } else {
      setPreview(null);
    }

    // Upload for OCR
    setUploading(true);
    try {
      const result = await uploadReceipt(f);
      setExtracted({
        ...result,
        amount: result.total_amount || result.amount,
        category: result.category || 'Uncategorized',
      });
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to parse receipt. Please ensure Tesseract OCR is installed.");
    } finally {
      setUploading(false);
    }
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!extracted) return;
    setSubmitting(true);
    try {
      let formattedDate = extracted.date;
      if (!formattedDate || !formattedDate.match(/^\d{4}-\d{2}-\d{2}$/)) {
        formattedDate = new Date().toISOString().split('T')[0];
      }

      if (!user?.employee_id) {
        setError("You must be logged in to submit an expense.");
        return;
      }
      await submitExpense({
        employee_id: user.employee_id,
        merchant_name: extracted.merchant || 'Unknown Merchant',
        amount: Number(extracted.amount),
        transaction_date: formattedDate,
        category: extracted.category || 'Office Supplies',
        receipt_path: extracted.receipt_path,
        user_remarks: extracted.remarks || '',
      });
      setSubmitted(true);
      if (onUploadComplete) onUploadComplete();
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to submit expense.");
    } finally {
      setSubmitting(false);
    }
  }, [extracted]);

  const resetUploader = useCallback(() => {
    setFile(null);
    setPreview(null);
    setExtracted(null);
    setSubmitted(false);
    setError(null);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/png': ['.png'],
      'image/jpeg': ['.jpg', '.jpeg'],
      'application/pdf': ['.pdf'],
    },
    maxFiles: 1,
    disabled: uploading,
  });

  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-fade-in-up">
      <div>
        <h2 className="text-2xl font-bold text-slate-100 mb-1">Upload Receipt</h2>
        <p className="text-sm text-slate-400">
          Drop a receipt image or PDF and our AI will extract expense details automatically.
        </p>
      </div>

      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={`relative glass-card p-10 text-center cursor-pointer transition-all duration-200 ${isDragActive
            ? 'border-teal-400 bg-teal-500/5 ring-2 ring-teal-500/20'
            : 'hover:border-slate-600 hover:bg-slate-800/60'
          } ${uploading ? 'pointer-events-none opacity-60' : ''}`}
      >
        <input {...getInputProps()} />

        {uploading ? (
          <div className="space-y-4">
            <FiLoader className="w-12 h-12 text-teal-400 mx-auto animate-spin" />
            <div>
              <p className="text-slate-200 font-medium">Processing receipt...</p>
              <p className="text-sm text-slate-400 mt-1">Extracting merchant, amount, and date via OCR</p>
            </div>
          </div>
        ) : file && preview ? (
          <div className="space-y-4">
            <img
              src={preview}
              alt="Receipt preview"
              className="max-h-48 mx-auto rounded-lg border border-slate-700/50 shadow-lg"
            />
            <div>
              <p className="text-slate-200 font-medium">{file.name}</p>
              <p className="text-sm text-slate-400">{(file.size / 1024).toFixed(1)} KB</p>
            </div>
          </div>
        ) : file ? (
          <div className="space-y-4">
            <FiImage className="w-12 h-12 text-slate-400 mx-auto" />
            <div>
              <p className="text-slate-200 font-medium">{file.name}</p>
              <p className="text-sm text-slate-400">{(file.size / 1024).toFixed(1)} KB</p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="w-16 h-16 mx-auto rounded-2xl bg-teal-500/10 flex items-center justify-center">
              <FiUploadCloud className="w-8 h-8 text-teal-400" />
            </div>
            <div>
              <p className="text-slate-200 font-medium">
                {isDragActive ? 'Drop your receipt here' : 'Drag & drop receipt here'}
              </p>
              <p className="text-sm text-slate-400 mt-1">
                or click to browse — PNG, JPG, PDF supported
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Extracted Data */}
      {extracted && !submitted && (
        <div className="glass-card p-6 space-y-5 animate-fade-in-up">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
              Extracted Details
            </h3>
            {extracted.confidence && (
              <span className="text-xs text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-full font-medium">
                {(extracted.confidence * 100).toFixed(0)}% confidence
              </span>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <EditableField
              icon={FiMapPin}
              label="Merchant"
              value={extracted.merchant}
              onChange={(val) => setExtracted({ ...extracted, merchant: val })}
            />
            <EditableField
              icon={FiDollarSign}
              label="Amount"
              type="number"
              readOnly={true}
              value={extracted.amount}
              onChange={(val) => setExtracted({ ...extracted, amount: val })}
              helpText={extracted.original_amount ? `Converted from ${extracted.original_currency} ${extracted.original_amount}` : null}
            />
            <EditableField
              icon={FiCalendar}
              label="Date"
              type="date"
              value={extracted.date}
              onChange={(val) => setExtracted({ ...extracted, date: val })}
            />
            <EditableField
              icon={FiTag}
              label="Category"
              value={extracted.category}
              onChange={(val) => setExtracted({ ...extracted, category: val })}
            />
          </div>

          <div className="flex flex-col gap-1 p-3 rounded-lg bg-slate-800/40 border border-slate-700/50 focus-within:border-teal-500/50 focus-within:bg-slate-800/60 transition-colors">
            <div className="flex items-center gap-2 text-slate-500 mb-1">
              <span className="text-xs uppercase tracking-wider font-semibold">Remarks (Optional)</span>
            </div>
            <textarea
              value={extracted.remarks || ''}
              onChange={(e) => setExtracted({ ...extracted, remarks: e.target.value })}
              className="w-full bg-transparent text-sm text-slate-200 font-medium focus:outline-none resize-none"
              placeholder="If the extracted amount is incorrect, please provide the correct amount and explanation here."
              rows={2}
            />
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={resetUploader}
              disabled={submitting}
              className="w-1/3 flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-slate-800/60 text-slate-300 font-semibold text-sm border border-slate-700/50 hover:bg-slate-700/60 transition-all disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={() => setShowSubmitConfirm(true)}
              disabled={submitting}
              className="flex-1 flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-teal-500/15 text-teal-400 font-semibold text-sm border border-teal-500/30 hover:bg-teal-500/25 hover:border-teal-500/50 disabled:opacity-50 transition-all"
            >
              {submitting ? (
                <>
                  <FiLoader className="w-4 h-4 animate-spin" />
                  Submitting...
                </>
              ) : (
                <>
                  <FiSend className="w-4 h-4" />
                  Submit as Expense
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Submit Confirmation Modal */}
      <ConfirmModal
        isOpen={showSubmitConfirm}
        title="Submit Expense Claim"
        message={`Are you sure you want to submit this expense claim${extracted?.amount ? ` for $${Number(extracted.amount).toFixed(2)}` : ''}? Once submitted, it will be processed by the AI compliance engine.`}
        confirmText="Yes, Submit"
        cancelText="Review Again"
        variant="info"
        onConfirm={() => { setShowSubmitConfirm(false); handleSubmit(); }}
        onCancel={() => setShowSubmitConfirm(false)}
      />

      {/* Success State */}
      {submitted && (
        <div className="glass-card p-8 text-center space-y-4 animate-fade-in-up">
          <div className="w-16 h-16 mx-auto rounded-full bg-emerald-500/15 flex items-center justify-center">
            <FiCheck className="w-8 h-8 text-emerald-400" />
          </div>
          <div>
            <p className="text-lg font-semibold text-slate-100">Expense Submitted!</p>
            <p className="text-sm text-slate-400 mt-1">
              Your expense claim has been submitted and will be processed by the AI engine.
            </p>
          </div>
          <button
            onClick={resetUploader}
            className="px-6 py-2.5 rounded-xl bg-slate-800/60 text-slate-300 font-medium text-sm border border-slate-700/50 hover:bg-slate-700/60 transition-all"
          >
            Upload Another Receipt
          </button>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="glass-card p-4 bg-rose-500/5 border-rose-500/20 text-rose-400 text-sm">
          {error}
        </div>
      )}
    </div>
  );
}

function EditableField({ icon: Icon, label, value, onChange, type = "text", helpText, readOnly = false }) {
  return (
    <div className={`flex flex-col gap-1 p-3 rounded-lg bg-slate-800/40 border border-slate-700/50 transition-colors ${readOnly ? 'opacity-80' : 'focus-within:border-teal-500/50 focus-within:bg-slate-800/60'}`}>
      <div className="flex items-center gap-2 text-slate-500">
        <Icon className="w-3.5 h-3.5" />
        <span className="text-xs uppercase tracking-wider font-semibold">{label}</span>
      </div>
      <input
        type={type}
        value={value || ''}
        readOnly={readOnly}
        onChange={(e) => !readOnly && onChange(e.target.value)}
        className={`w-full bg-transparent text-sm font-medium focus:outline-none text-slate-200 ${readOnly ? 'cursor-not-allowed' : ''}`}
      />
      {helpText && <div className="text-[10px] text-slate-500">{helpText}</div>}
    </div>
  );
}
