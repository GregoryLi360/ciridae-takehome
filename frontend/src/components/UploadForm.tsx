import { useCallback, useState } from "react";
import { Upload, FileText, ArrowRight } from "lucide-react";
import { z } from "zod";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const PdfFile = z.instanceof(File).refine(
  (f) => f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf"),
  { message: "File must be a PDF" }
);

const UploadSchema = z.object({
  jdr: PdfFile,
  insurance: PdfFile,
});

interface Props {
  onSubmit: (files: { jdr: File; insurance: File }) => void;
  isLoading: boolean;
  error?: string | null;
}

function Dropzone({
  label,
  sublabel,
  file,
  onFile,
}: {
  label: string;
  sublabel: string;
  file: File | null;
  onFile: (f: File) => void;
}) {
  const [dragOver, setDragOver] = useState(false);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const f = e.dataTransfer.files[0];
      if (f && PdfFile.safeParse(f).success) onFile(f);
    },
    [onFile]
  );

  return (
    <label
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      className={cn(
        "relative flex flex-col items-center justify-center gap-4",
        "border border-dashed p-16 cursor-pointer transition-all duration-200",
        dragOver
          ? "border-foreground bg-accent"
          : file
            ? "border-foreground/30 bg-accent/50"
            : "border-border hover:border-foreground/40"
      )}
    >
      <input
        type="file"
        accept=".pdf"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
        }}
      />
      {file ? (
        <>
          <FileText className="w-6 h-6 text-foreground/60" strokeWidth={1.5} />
          <div className="text-center">
            <p className="text-sm font-medium">{file.name}</p>
            <p className="text-xs text-muted-foreground mt-1">
              {(file.size / 1024 / 1024).toFixed(1)} MB
            </p>
          </div>
        </>
      ) : (
        <>
          <Upload className="w-6 h-6 text-muted-foreground" strokeWidth={1.5} />
          <div className="text-center">
            <p className="font-mono text-sm font-medium uppercase tracking-[0.08em]">
              {label}
            </p>
            <p className="text-xs text-muted-foreground mt-2">{sublabel}</p>
          </div>
        </>
      )}
    </label>
  );
}

export default function UploadForm({ onSubmit, isLoading, error }: Props) {
  const [jdr, setJdr] = useState<File | null>(null);
  const [ins, setIns] = useState<File | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const ready = jdr && ins && !isLoading;

  const handleSubmit = () => {
    if (!jdr || !ins) return;
    const result = UploadSchema.safeParse({ jdr, insurance: ins });
    if (!result.success) {
      setValidationError(result.error.issues[0].message);
      return;
    }
    setValidationError(null);
    onSubmit(result.data);
  };

  return (
    <section className="min-h-[calc(100vh-72px)] flex items-center">
      <div className="max-w-[1600px] mx-auto px-8 w-full py-24">
        <div className="max-w-3xl mb-20">
          <p className="font-mono text-xs tracking-[0.08em] uppercase text-muted-foreground mb-6">
            01 — Upload
          </p>
          <h1 className="font-mono text-4xl md:text-5xl font-semibold tracking-[-0.03em] leading-[0.95] uppercase">
            Compare Proposals
          </h1>
          <p className="mt-8 text-muted-foreground text-lg leading-relaxed max-w-xl">
            Upload both the JDR contractor proposal and the insurance
            adjuster's estimate to match line items and identify discrepancies.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-6 max-w-3xl">
          <Dropzone
            label="JDR Proposal"
            sublabel="Contractor's PDF estimate"
            file={jdr}
            onFile={setJdr}
          />
          <Dropzone
            label="Insurance Estimate"
            sublabel="Adjuster's PDF estimate"
            file={ins}
            onFile={setIns}
          />
        </div>

        <Button
          type="button"
          disabled={!ready}
          onClick={handleSubmit}
          className="mt-12"
        >
          {isLoading ? "Uploading..." : "Analyze proposals"}
          <ArrowRight className="w-4 h-4" strokeWidth={1.5} />
        </Button>

        {(error || validationError) && (
          <p className="mt-4 text-sm text-red-400">{validationError || error}</p>
        )}
      </div>
    </section>
  );
}
