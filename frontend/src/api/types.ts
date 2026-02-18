export type JobStatus =
  | "pending"
  | "parsing"
  | "matching"
  | "annotating"
  | "complete"
  | "error";

export interface JobResponse {
  id: string;
  status: JobStatus;
  progress?: string;
  summary?: {
    total_jdr_items: number;
    total_ins_items: number;
    matched_green: number;
    matched_orange: number;
    unmatched_blue: number;
    unmatched_nugget: number;
  };
  error?: string;
}

export interface LineItem {
  description: string;
  quantity: number | null;
  unit: string | null;
  unit_price: number | null;
  total: number | null;
  page_number: number;
}

export interface DiffNote {
  field: string;
  jdr_value: string;
  ins_value: string;
}

export interface MatchedPair {
  jdr_item: LineItem;
  ins_item: LineItem;
  color: "green" | "orange";
  diff_notes: DiffNote[];
}

export interface RoomComparison {
  jdr_room: string | null;
  ins_room: string | null;
  matched: MatchedPair[];
  unmatched_jdr: LineItem[];
  unmatched_ins: LineItem[];
}

export interface ItemsResponse {
  rooms: RoomComparison[];
}
