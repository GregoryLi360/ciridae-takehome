import { Loader2, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import type { JobResponse } from "@/api/types";

const STAGES = [
  { key: "parsing", label: "Parsing documents" },
  { key: "matching", label: "Matching line items" },
  { key: "annotating", label: "Generating annotated PDF" },
  { key: "complete", label: "Complete" },
] as const;

const STAGE_KEYS = STAGES.map((s) => s.key);

interface Props {
  job: JobResponse;
}

export default function JobStatusView({ job }: Props) {
  const currentIdx = STAGE_KEYS.indexOf(
    job.status as (typeof STAGE_KEYS)[number]
  );

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

          <div className="mt-20 space-y-6">
            {STAGES.map((stage, idx) => {
              const isActive = stage.key === job.status;
              const isDone = idx < currentIdx;
              const isPending = idx > currentIdx;

              let progress = 0;
              if (isDone) {
                progress = 100;
              } else if (isActive && job.total_steps > 0) {
                progress = Math.round((job.step / job.total_steps) * 100);
              }

              return (
                <div key={stage.key}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <div className="w-5 flex items-center justify-center">
                        {isActive && stage.key !== "complete" ? (
                          <Loader2
                            className="w-4 h-4 animate-spin text-foreground"
                            strokeWidth={1.5}
                          />
                        ) : isDone || (isActive && stage.key === "complete") ? (
                          <Check
                            className="w-4 h-4 text-foreground"
                            strokeWidth={2}
                          />
                        ) : (
                          <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground/30" />
                        )}
                      </div>
                      <span
                        className={cn(
                          "font-mono text-sm uppercase tracking-[0.08em]",
                          isPending
                            ? "text-muted-foreground/40"
                            : "text-foreground"
                        )}
                      >
                        {stage.label}
                      </span>
                    </div>
                    {(isActive || isDone) && stage.key !== "complete" && (
                      <span className="font-mono text-xs text-muted-foreground tabular-nums">
                        {progress}%
                      </span>
                    )}
                  </div>

                  {stage.key !== "complete" && (
                    <div className="ml-8 h-1 bg-muted rounded-full overflow-hidden">
                      <div
                        className={cn(
                          "h-full rounded-full transition-all duration-1000 ease-out",
                          isDone || isActive
                            ? "bg-foreground"
                            : "bg-transparent"
                        )}
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                  )}

                  {isActive && job.progress && stage.key !== "complete" && (
                    <p className="ml-8 mt-2 text-xs text-muted-foreground">
                      {job.progress}
                    </p>
                  )}
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
