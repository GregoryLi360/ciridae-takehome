import type { JobResponse, ItemsResponse } from "./types";

export const MOCK_JOB_COMPLETE: JobResponse = {
  id: "demo-001",
  status: "complete",
  summary: {
    total_jdr_items: 181,
    total_ins_items: 95,
    matched_green: 11,
    matched_orange: 62,
    unmatched_blue: 108,
    unmatched_nugget: 22,
  },
};

export const MOCK_ITEMS: ItemsResponse = {
  rooms: [
    {
      jdr_rooms: ["Bathroom"],
      ins_rooms: ["Hall Bathroom"],
      matched: [
        {
          jdr_item: {
            description: "Batt insulation replacement per LF - 4\" - up to 2' tall",
            quantity: 5.42, unit: "LF", unit_price: 10.06, total: 54.55, page_number: 2,
          },
          ins_item: {
            description: "Batt insulation - 4\" - R11- unfaced batt",
            quantity: 45.0, unit: "SF", unit_price: 1.93, total: 86.85, page_number: 3,
          },
          color: "orange",
          diff_notes: [
            { field: "unit", jdr_value: "LF", ins_value: "SF" },
            { field: "quantity", jdr_value: "5.42", ins_value: "45.0" },
          ],
        },
        {
          jdr_item: {
            description: "1/2\" - drywall per LF - up to 2' tall",
            quantity: 11.5, unit: "LF", unit_price: 5.03, total: 57.85, page_number: 3,
          },
          ins_item: {
            description: "1/2\" - drywall per LF - up to 2' tall",
            quantity: 14.33, unit: "LF", unit_price: 5.03, total: 72.08, page_number: 3,
          },
          color: "orange",
          diff_notes: [
            { field: "quantity", jdr_value: "11.5", ins_value: "14.33" },
          ],
        },
        {
          jdr_item: {
            description: "Vanity",
            quantity: 2.58, unit: "LF", unit_price: 207.68, total: 535.81, page_number: 3,
          },
          ins_item: {
            description: "Vanity - standard",
            quantity: 3.0, unit: "LF", unit_price: 207.68, total: 623.04, page_number: 4,
          },
          color: "orange",
          diff_notes: [
            { field: "quantity", jdr_value: "2.58", ins_value: "3.0" },
          ],
        },
        {
          jdr_item: {
            description: "Door opening (jamb & casing) - 32\"to36\"wide - paint grade",
            quantity: 1.0, unit: "EA", unit_price: 179.14, total: 179.14, page_number: 4,
          },
          ins_item: {
            description: "Door opening (jamb & casing) - 32\"to36\"wide - paint grade",
            quantity: 1.0, unit: "EA", unit_price: 179.06, total: 179.06, page_number: 5,
          },
          color: "green",
          diff_notes: [],
        },
        {
          jdr_item: {
            description: "Interior door - Reset - slab only",
            quantity: 1.0, unit: "EA", unit_price: 13.77, total: 13.77, page_number: 4,
          },
          ins_item: {
            description: "Interior door - Reset - slab only",
            quantity: 1.0, unit: "EA", unit_price: 13.75, total: 13.75, page_number: 5,
          },
          color: "green",
          diff_notes: [],
        },
      ],
      unmatched_jdr: [
        { description: "R&R 1/2\" drywall - hung, taped, floated, ready for paint", quantity: 8.0, unit: "SF", unit_price: 4.82, total: 38.56, page_number: 3 },
        { description: "Seal & paint vanity - inside and out", quantity: 4.58, unit: "LF", unit_price: 6.33, total: 28.99, page_number: 3 },
        { description: "Vanity top - one sink - cultured marble", quantity: 1.0, unit: "EA", unit_price: 273.55, total: 273.55, page_number: 3 },
        { description: "P-trap assembly - ABS (plastic)", quantity: 1.0, unit: "EA", unit_price: 64.51, total: 64.51, page_number: 3 },
        { description: "Detach & Reset Mirror - framed", quantity: 1.0, unit: "EA", unit_price: 27.57, total: 27.57, page_number: 3 },
        { description: "HEPA Vacuuming - Light - (PER SF)", quantity: 52.0, unit: "SF", unit_price: 0.82, total: 42.64, page_number: 3 },
        { description: "Grout sealer", quantity: 22.28, unit: "SF", unit_price: 0.67, total: 14.93, page_number: 4 },
        { description: "Mask wall - plastic, paper, tape (per LF)", quantity: 19.17, unit: "LF", unit_price: 2.75, total: 52.72, page_number: 4 },
      ],
      unmatched_ins: [
        { description: "Tape joint for new to existing drywall - per LF", quantity: 19.33, unit: "LF", unit_price: 1.05, total: 20.3, page_number: 4 },
      ],
    },
    {
      jdr_rooms: ["Laundry Room"],
      ins_rooms: ["Laundry Room"],
      matched: [
        {
          jdr_item: {
            description: "Washer/Washing machine - Remove & reset",
            quantity: 1.0, unit: "EA", unit_price: 46.63, total: 46.63, page_number: 6,
          },
          ins_item: {
            description: "Detach & Reset Washer - front loading",
            quantity: 1.0, unit: "EA", unit_price: 53.82, total: 53.82, page_number: 5,
          },
          color: "orange",
          diff_notes: [
            { field: "unit_price", jdr_value: "46.63", ins_value: "53.82" },
          ],
        },
        {
          jdr_item: {
            description: "Dryer - Remove & reset",
            quantity: 1.0, unit: "EA", unit_price: 37.06, total: 37.06, page_number: 6,
          },
          ins_item: {
            description: "Detach & Reset Dryer - Electric",
            quantity: 1.0, unit: "EA", unit_price: 37.06, total: 37.06, page_number: 5,
          },
          color: "orange",
          diff_notes: [
            { field: "unit_price", jdr_value: "37.06", ins_value: "37.06" },
          ],
        },
      ],
      unmatched_jdr: [
        { description: "Concrete grinding", quantity: 37.05, unit: "SF", unit_price: 3.13, total: 115.97, page_number: 5 },
        { description: "Mortar bed for tile floors", quantity: 37.05, unit: "SF", unit_price: 4.69, total: 173.76, page_number: 6 },
        { description: "Door stop - wall or floor mounted", quantity: 1.0, unit: "EA", unit_price: 18.04, total: 18.04, page_number: 6 },
      ],
      unmatched_ins: [
        { description: "Detach & Reset Shelving - 12\" - in place", quantity: 7.0, unit: "LF", unit_price: 7.22, total: 50.54, page_number: 5 },
        { description: "Seal & paint wood shelving, 12\"-24\" width", quantity: 7.0, unit: "LF", unit_price: 3.23, total: 22.61, page_number: 5 },
      ],
    },
    {
      jdr_rooms: ["Garage"],
      ins_rooms: ["Garage"],
      matched: [
        {
          jdr_item: {
            description: "Baseboard - 3 1/4\"",
            quantity: 17.0, unit: "LF", unit_price: 4.62, total: 78.54, page_number: 7,
          },
          ins_item: {
            description: "Baseboard - 3 1/4\" MDF w/profile",
            quantity: 17.0, unit: "LF", unit_price: 4.62, total: 78.54, page_number: 6,
          },
          color: "green",
          diff_notes: [],
        },
      ],
      unmatched_jdr: [
        { description: "On site door prep. for full mortised hinges - Labor only", quantity: 1.0, unit: "EA", unit_price: 53.67, total: 53.67, page_number: 7 },
        { description: "Mask wall - plastic, paper, tape (per LF)", quantity: 20.0, unit: "LF", unit_price: 2.75, total: 55.0, page_number: 7 },
        { description: "Floor protection - plastic and tape - 10 mil", quantity: 407.24, unit: "SF", unit_price: 0.22, total: 89.59, page_number: 7 },
      ],
      unmatched_ins: [
        { description: "Freezer - Remove & reset", quantity: 1.0, unit: "EA", unit_price: 42.94, total: 42.94, page_number: 6 },
      ],
    },
    {
      jdr_rooms: ["Bedroom 1"],
      ins_rooms: ["Bedroom"],
      matched: [
        {
          jdr_item: {
            description: "Door opening (jamb & casing) - 32\"to36\"wide - paint grade",
            quantity: 1.0, unit: "EA", unit_price: 179.14, total: 179.14, page_number: 11,
          },
          ins_item: {
            description: "Door opening (jamb & casing) - 32\"to36\"wide - paint grade",
            quantity: 1.0, unit: "EA", unit_price: 179.06, total: 179.06, page_number: 10,
          },
          color: "green",
          diff_notes: [],
        },
        {
          jdr_item: {
            description: "Carpet",
            quantity: 138.12, unit: "SF", unit_price: 3.88, total: 535.91, page_number: 11,
          },
          ins_item: {
            description: "Carpet - per specs from independent carpet analysis",
            quantity: 161.83, unit: "SF", unit_price: 4.67, total: 755.75, page_number: 10,
          },
          color: "orange",
          diff_notes: [
            { field: "quantity", jdr_value: "138.12", ins_value: "161.83" },
            { field: "unit_price", jdr_value: "3.88", ins_value: "4.67" },
          ],
        },
      ],
      unmatched_jdr: [
        { description: "Cold air return cover - Detach & reset", quantity: 1.0, unit: "EA", unit_price: 18.04, total: 18.04, page_number: 11 },
        { description: "Mask wall - plastic, paper, tape (per LF)", quantity: 42.95, unit: "LF", unit_price: 2.75, total: 118.11, page_number: 11 },
        { description: "Content Manipulation charge - per hour", quantity: 2.0, unit: "HR", unit_price: 34.33, total: 68.66, page_number: 11 },
      ],
      unmatched_ins: [
        { description: "Tape joint for new to existing drywall - per LF", quantity: 14.0, unit: "LF", unit_price: 1.05, total: 14.7, page_number: 9 },
        { description: "Texture drywall - light hand texture", quantity: 56.0, unit: "SF", unit_price: 0.71, total: 39.76, page_number: 9 },
      ],
    },
    {
      jdr_rooms: ["Living Room"],
      ins_rooms: ["Living Room"],
      matched: [
        {
          jdr_item: {
            description: "Remove Carpet",
            quantity: 321.11, unit: "SF", unit_price: 0.3, total: 96.33, page_number: 13,
          },
          ins_item: {
            description: "Remove Carpet",
            quantity: 321.01, unit: "SF", unit_price: 0.3, total: 96.3, page_number: 11,
          },
          color: "orange",
          diff_notes: [
            { field: "quantity", jdr_value: "321.11", ins_value: "321.01" },
          ],
        },
        {
          jdr_item: {
            description: "Carpet",
            quantity: 321.11, unit: "SF", unit_price: 3.88, total: 1245.91, page_number: 13,
          },
          ins_item: {
            description: "Carpet - per specs from independent carpet analysis",
            quantity: 383.08, unit: "SF", unit_price: 4.67, total: 1788.98, page_number: 11,
          },
          color: "orange",
          diff_notes: [
            { field: "quantity", jdr_value: "321.11", ins_value: "383.08" },
            { field: "unit_price", jdr_value: "3.88", ins_value: "4.67" },
          ],
        },
      ],
      unmatched_jdr: [
        { description: "Seal/prime (1 coat) then paint (2 coats) the walls", quantity: 482.95, unit: "SF", unit_price: 1.14, total: 550.56, page_number: 12 },
        { description: "Baseboard - 3 1/4\"", quantity: 1.17, unit: "LF", unit_price: 4.62, total: 5.41, page_number: 12 },
        { description: "Window drapery - hardware - Detach & reset", quantity: 1.0, unit: "EA", unit_price: 42.22, total: 42.22, page_number: 13 },
        { description: "Content Manipulation (Bid Item)", quantity: 1.0, unit: "EA", unit_price: null, total: null, page_number: 13 },
      ],
      unmatched_ins: [
        { description: "Carpet - per specs from independent carpet analysis (Offset)", quantity: 66.17, unit: "SF", unit_price: 4.67, total: 309.01, page_number: 11 },
      ],
    },
    {
      jdr_rooms: ["Formal Dining Room"],
      ins_rooms: ["Dining Room"],
      matched: [
        {
          jdr_item: {
            description: "Remove Carpet",
            quantity: 163.4, unit: "SF", unit_price: 0.3, total: 49.02, page_number: 14,
          },
          ins_item: {
            description: "Remove Carpet",
            quantity: 163.4, unit: "SF", unit_price: 0.3, total: 49.02, page_number: 12,
          },
          color: "green",
          diff_notes: [],
        },
        {
          jdr_item: {
            description: "Carpet",
            quantity: 163.4, unit: "SF", unit_price: 3.88, total: 633.99, page_number: 14,
          },
          ins_item: {
            description: "Carpet - per specs from independent carpet analysis",
            quantity: 170.83, unit: "SF", unit_price: 4.67, total: 797.78, page_number: 12,
          },
          color: "orange",
          diff_notes: [
            { field: "quantity", jdr_value: "163.4", ins_value: "170.83" },
            { field: "unit_price", jdr_value: "3.88", ins_value: "4.67" },
          ],
        },
      ],
      unmatched_jdr: [
        { description: "R&R Carpet pad", quantity: 163.4, unit: "SF", unit_price: 1.05, total: 171.57, page_number: 14 },
      ],
      unmatched_ins: [],
    },
  ],
};
