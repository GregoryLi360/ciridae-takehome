import { useState } from "react";
import { Download, ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from "@/components/ui/collapsible";
import type { JobResponse, ItemsResponse } from "@/api/types";

const COLOR_CONFIG = {
  green: {
    bg: "bg-match/5",
    border: "border-match/20",
    dot: "bg-match",
    variant: "match" as const,
  },
  orange: {
    bg: "bg-diff/5",
    border: "border-diff/20",
    dot: "bg-diff",
    variant: "diff" as const,
  },
  blue: {
    bg: "bg-jdr-only/5",
    border: "border-jdr-only/20",
    dot: "bg-jdr-only",
    variant: "jdrOnly" as const,
  },
  nugget: {
    bg: "bg-ins-only/5",
    border: "border-ins-only/20",
    dot: "bg-ins-only",
    variant: "insOnly" as const,
  },
} as const;

function StatCard({
  value,
  label,
  dotColor,
}: {
  value: number;
  label: string;
  dotColor: string;
}) {
  return (
    <Card>
      <CardContent className="p-6">
        <div className={cn("w-2 h-2", dotColor, "mb-4")} />
        <p className="text-3xl font-semibold tracking-[-0.02em]">{value}</p>
        <p className="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground mt-1">
          {label}
        </p>
      </CardContent>
    </Card>
  );
}

function RoomSection({
  room,
  index,
}: {
  room: ItemsResponse["rooms"][number];
  index: number;
}) {
  const [open, setOpen] = useState(index === 0);
  const jdrLabel = room.jdr_room ?? "\u2014";
  const insLabel = room.ins_room ?? "\u2014";
  const total =
    room.matched.length + room.unmatched_jdr.length + room.unmatched_ins.length;

  const greenCount = room.matched.filter((p) => p.color === "green").length;
  const orangeCount = room.matched.filter((p) => p.color === "orange").length;

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger onClick={() => setOpen(!open)}>
        {open ? (
          <ChevronDown
            className="w-4 h-4 text-muted-foreground shrink-0"
            strokeWidth={1.5}
          />
        ) : (
          <ChevronRight
            className="w-4 h-4 text-muted-foreground shrink-0"
            strokeWidth={1.5}
          />
        )}
        <div className="flex-1 min-w-0">
          <p className="font-mono text-sm font-medium uppercase tracking-[0.08em] truncate">
            {jdrLabel}
          </p>
          {insLabel !== jdrLabel && (
            <p className="text-xs text-muted-foreground mt-0.5 truncate">
              &harr; {insLabel}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {greenCount > 0 && (
            <Badge variant="match">
              <span className="w-1.5 h-1.5 bg-match" />
              {greenCount}
            </Badge>
          )}
          {orangeCount > 0 && (
            <Badge variant="diff">
              <span className="w-1.5 h-1.5 bg-diff" />
              {orangeCount}
            </Badge>
          )}
          {room.unmatched_jdr.length > 0 && (
            <Badge variant="jdrOnly">
              <span className="w-1.5 h-1.5 bg-jdr-only" />
              {room.unmatched_jdr.length}
            </Badge>
          )}
          {room.unmatched_ins.length > 0 && (
            <Badge variant="insOnly">
              <span className="w-1.5 h-1.5 bg-ins-only" />
              {room.unmatched_ins.length}
            </Badge>
          )}
          <span className="text-xs text-muted-foreground/50 ml-2">
            {total} items
          </span>
        </div>
      </CollapsibleTrigger>

      {open && (
        <CollapsibleContent>
          {room.matched.map((pair, i) => {
            const cfg = COLOR_CONFIG[pair.color];
            return (
              <div
                key={i}
                className={cn(
                  cfg.bg,
                  "border-b",
                  cfg.border,
                  "last:border-b-0"
                )}
              >
                <div className="px-5 py-3 flex items-start gap-4">
                  <span
                    className={cn(
                      "w-2 h-2 mt-1.5 shrink-0",
                      cfg.dot
                    )}
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm">{pair.jdr_item.description}</p>
                    {pair.diff_notes.length > 0 && (
                      <div className="mt-2 space-y-1">
                        {pair.diff_notes.map((d, j) => (
                          <p
                            key={j}
                            className="text-xs text-muted-foreground"
                          >
                            <span className="font-mono uppercase">
                              {d.field}
                            </span>
                            :{" "}
                            <span className="text-foreground/70">
                              {d.jdr_value}
                            </span>
                            {" \u2192 "}
                            <span className="text-foreground/70">
                              {d.ins_value}
                            </span>
                          </p>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-sm font-mono">
                      {pair.jdr_item.total != null
                        ? `$${pair.jdr_item.total.toLocaleString()}`
                        : "\u2014"}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}

          {room.unmatched_jdr.map((item, i) => (
            <div
              key={`b${i}`}
              className="bg-jdr-only/5 border-b border-jdr-only/20 last:border-b-0"
            >
              <div className="px-5 py-3 flex items-start gap-4">
                <span className="w-2 h-2 bg-jdr-only mt-1.5 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm">{item.description}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    JDR only
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-sm font-mono">
                    {item.total != null
                      ? `$${item.total.toLocaleString()}`
                      : "\u2014"}
                  </p>
                </div>
              </div>
            </div>
          ))}

          {room.unmatched_ins.map((item, i) => (
            <div
              key={`n${i}`}
              className="bg-ins-only/5 border-b border-ins-only/20 last:border-b-0"
            >
              <div className="px-5 py-3 flex items-start gap-4">
                <span className="w-2 h-2 bg-ins-only mt-1.5 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm">{item.description}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Insurance only
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-sm font-mono">
                    {item.total != null
                      ? `$${item.total.toLocaleString()}`
                      : "\u2014"}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </CollapsibleContent>
      )}
    </Collapsible>
  );
}

interface Props {
  job: JobResponse;
  items: ItemsResponse | undefined;
}

export default function ResultViewer({ job, items }: Props) {
  const summary = job.summary;

  return (
    <section className="min-h-[calc(100vh-72px)]">
      <div className="bg-muted/60 backdrop-blur-sm border-b border-border">
        <div className="max-w-[1600px] mx-auto px-8 py-20">
          <div className="flex items-end justify-between mb-12">
            <div>
              <p className="font-mono text-xs tracking-[0.08em] uppercase text-muted-foreground mb-6">
                03 — Results
              </p>
              <h2 className="font-mono text-3xl md:text-4xl font-semibold tracking-[-0.03em] leading-[0.95] uppercase">
                Comparison Complete
              </h2>
            </div>
            <a
              href={`/api/jobs/${job.id}/result`}
              download
              className={buttonVariants()}
            >
              Download PDF
              <Download className="w-4 h-4" strokeWidth={1.5} />
            </a>
          </div>

          {summary && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard
                value={summary.matched_green}
                label="Exact Match"
                dotColor="bg-match"
              />
              <StatCard
                value={summary.matched_orange}
                label="Differences"
                dotColor="bg-diff"
              />
              <StatCard
                value={summary.unmatched_blue}
                label="JDR Only"
                dotColor="bg-jdr-only"
              />
              <StatCard
                value={summary.unmatched_nugget}
                label="Insurance Only"
                dotColor="bg-ins-only"
              />
            </div>
          )}
        </div>
      </div>

      <div className="bg-background/90 backdrop-blur-sm">
        <div className="max-w-[1600px] mx-auto px-8 py-20">
          <p className="font-mono text-xs tracking-[0.08em] uppercase text-muted-foreground mb-10">
            Room-by-room breakdown
          </p>
          {items ? (
            <div className="space-y-3">
              {items.rooms.map((room, i) => (
                <RoomSection key={i} room={room} index={i} />
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground">Loading items...</p>
          )}
        </div>
      </div>
    </section>
  );
}
