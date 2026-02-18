import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { JobResponse } from "@/api/types";

const STAGE_LABELS: Record<string, string> = {
  pending: "Queued",
  parsing: "Parsing documents",
  matching: "Matching line items",
  annotating: "Generating annotated PDF",
  complete: "Complete",
  error: "Error",
};

const STAGE_ORDER = [
  "parsing",
  "matching",
  "annotating",
  "complete",
];

interface Props {
  job: JobResponse;
}

export default function JobStatusView({ job }: Props) {
  const currentIdx = STAGE_ORDER.indexOf(job.status);

  return (
    <section className="min-h-[calc(100vh-72px)] flex items-center">
      <div className="max-w-[1600px] mx-auto px-8 w-full py-24">
        <div className="max-w-xl">
          <p className="font-mono text-xs tracking-[0.08em] uppercase text-muted-foreground mb-6">
            02 — Processing
          </p>
          <h2 className="font-mono text-3xl md:text-4xl font-semibold tracking-[-0.03em] leading-[0.95] uppercase">
            Analyzing
          </h2>
          <p className="mt-8 text-muted-foreground leading-relaxed">
            Extracting line items, mapping rooms, and matching proposals.
          </p>

          <div className="mt-20">
            {STAGE_ORDER.map((stage, idx) => {
              const isActive = stage === job.status;
              const isDone = idx < currentIdx;
              const isPending = idx > currentIdx;

              return (
                <div
                  key={stage}
                  className={cn(
                    "flex items-center gap-4 py-4",
                    idx > 0 && "border-t border-border"
                  )}
                >
                  <div className="w-6 flex items-center justify-center">
                    {isActive ? (
                      <Loader2
                        className="w-4 h-4 animate-spin text-foreground"
                        strokeWidth={1.5}
                      />
                    ) : isDone ? (
                      <div className="w-1.5 h-1.5 bg-foreground" />
                    ) : (
                      <div className="w-1.5 h-1.5 bg-border" />
                    )}
                  </div>
                  <span
                    className={cn(
                      "font-mono text-sm uppercase tracking-[0.08em]",
                      isPending ? "text-muted-foreground/40" : "text-foreground"
                    )}
                  >
                    {STAGE_LABELS[stage] || stage}
                  </span>
                </div>
              );
            })}
          </div>

          {job.status === "error" && (
            <div className="mt-10 p-5 border border-red-500/30 bg-red-500/10 text-red-400 text-sm">
              {job.error || "An unexpected error occurred."}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
