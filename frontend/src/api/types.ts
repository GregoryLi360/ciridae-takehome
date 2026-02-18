import { z } from "zod";

export const JobStatus = z.enum([
  "pending",
  "parsing_jdr",
  "parsing_insurance",
  "matching",
  "annotating",
  "complete",
  "error",
]);
export type JobStatus = z.infer<typeof JobStatus>;

export const JobResponse = z.object({
  id: z.string(),
  status: JobStatus,
  progress: z.string().optional(),
  summary: z
    .object({
      total_jdr_items: z.number(),
      total_ins_items: z.number(),
      matched_green: z.number(),
      matched_orange: z.number(),
      unmatched_blue: z.number(),
      unmatched_nugget: z.number(),
    })
    .optional(),
  error: z.string().optional(),
});
export type JobResponse = z.infer<typeof JobResponse>;

export const LineItem = z.object({
  description: z.string(),
  quantity: z.number().nullable(),
  unit: z.string().nullable(),
  unit_price: z.number().nullable(),
  total: z.number().nullable(),
  page_number: z.number(),
});

export const MatchedPair = z.object({
  jdr_item: LineItem,
  ins_item: LineItem,
  color: z.enum(["green", "orange"]),
  diff_notes: z.array(
    z.object({
      field: z.string(),
      jdr_value: z.string(),
      ins_value: z.string(),
    })
  ),
});

export const RoomComparison = z.object({
  jdr_rooms: z.array(z.string()),
  ins_rooms: z.array(z.string()),
  matched: z.array(MatchedPair),
  unmatched_jdr: z.array(LineItem),
  unmatched_ins: z.array(LineItem),
});

export const ItemsResponse = z.object({
  rooms: z.array(RoomComparison),
});
export type ItemsResponse = z.infer<typeof ItemsResponse>;
