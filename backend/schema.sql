-- TraceReady database schema (SQLite).
-- The two event tables follow the FDA FSMA 204 sortable spreadsheet template column for column.
-- Location blocks use the same 7 fields everywhere: name, phone, street, city, state, zip, country.

-- Who we trade with (and ourselves)
CREATE TABLE trading_partners (
  id            INTEGER PRIMARY KEY,
  name          TEXT NOT NULL UNIQUE,
  role          TEXT NOT NULL CHECK (role IN ('self', 'supplier', 'customer', 'regulator')),
  contact       TEXT,
  email         TEXT,
  phone         TEXT,
  street        TEXT,
  city          TEXT,
  state         TEXT,
  zip           TEXT,
  country       TEXT
);

-- Product master: how each product is described in FDA records
CREATE TABLE products (
  name          TEXT PRIMARY KEY,
  commodity     TEXT,
  variety       TEXT,
  pack_size     TEXT,
  pack_style    TEXT,
  gtin          TEXT
);

-- One row per Traceability Lot Code we have received
CREATE TABLE lots (
  tlc              TEXT PRIMARY KEY,
  product          TEXT REFERENCES products(name),
  supplier         TEXT,
  tlc_source       TEXT,
  received_qty     INTEGER,
  shipped_qty      INTEGER,
  on_hand_qty      INTEGER,
  status           TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'recalled'))
);

-- Every piece of work: receiving review, shipment confirmation, FDA request, recall
CREATE TABLE cases (
  id            TEXT PRIMARY KEY,               -- TR-2026-0420, SH-2026-0131, INC-2026-0007 ...
  kind          TEXT NOT NULL CHECK (kind IN ('receiving', 'shipping', 'fda_request', 'recall', 'incident')),
  status        TEXT NOT NULL CHECK (status IN ('new_update', 'pending', 'complete')),
  title         TEXT,
  supplier      TEXT,
  products      TEXT,
  lots          TEXT,                           -- comma separated TLCs
  owner         TEXT,                           -- person who created the case
  signer        TEXT,                           -- person who signed it complete
  created_at    TEXT,                           -- local time, ISO 8601
  updated_at    TEXT,
  completed_at  TEXT,
  reasons       TEXT                            -- why it is still open (JSON list)
);

-- Source files: uploaded receiving documents and email attachments
CREATE TABLE documents (
  id            INTEGER PRIMARY KEY,
  case_id       TEXT,
  email_id      INTEGER REFERENCES emails(id),
  filename      TEXT NOT NULL,
  doc_type      TEXT NOT NULL,                  -- invoice, packing_slip, bill_of_lading, pallet_label, delivery_receipt, lot_label_photo, destroyed_photo, destruction_form
  path          TEXT,                           -- relative to data/
  source        TEXT NOT NULL CHECK (source IN ('upload', 'email'))
);

-- The connected inbox (in) and messages we send (out)
CREATE TABLE emails (
  id            INTEGER PRIMARY KEY,
  direction     TEXT NOT NULL CHECK (direction IN ('in', 'out')),
  message_id    TEXT,
  event_key     TEXT,                           -- story event that delivers this email (timeline.json)
  case_id       TEXT,
  from_addr     TEXT,
  to_addr       TEXT,
  subject       TEXT,
  body          TEXT,
  sent_at       TEXT,                           -- Date header, local time
  imported_at   TEXT,                           -- NULL until the demo clock reaches sent_at
  file          TEXT                            -- .eml file in data/inbox/
);

-- What the AI read from a document or email
CREATE TABLE extractions (
  id            INTEGER PRIMARY KEY,
  email_id      INTEGER REFERENCES emails(id),
  source_file   TEXT,
  kind          TEXT,                           -- receiving_documents, supplier_lot_reply, delivery_receipt, recall_reply, fda_request
  fields_json   TEXT NOT NULL,
  method        TEXT NOT NULL,                  -- fixture (expected/*.json) or llm
  created_at    TEXT
);

-- FSMA 204 Critical Tracking Event: RECEIVING (FDA template, 36 columns)
CREATE TABLE receiving_events (
  id INTEGER PRIMARY KEY,
  case_id TEXT,
  tlc TEXT, quantity TEXT, unit_of_measure TEXT,
  product_name TEXT, brand_name TEXT, commodity TEXT, variety TEXT, packaging_size TEXT, packaging_style TEXT,
  prev_source_name TEXT, prev_source_phone TEXT, prev_source_street TEXT, prev_source_city TEXT, prev_source_state TEXT, prev_source_zip TEXT, prev_source_country TEXT,
  received_at_name TEXT, received_at_phone TEXT, received_at_street TEXT, received_at_city TEXT, received_at_state TEXT, received_at_zip TEXT, received_at_country TEXT,
  receive_date TEXT,
  tlc_source_name TEXT, tlc_source_phone TEXT, tlc_source_street TEXT, tlc_source_city TEXT, tlc_source_state TEXT, tlc_source_zip TEXT, tlc_source_country TEXT,
  tlc_source_reference TEXT, ref_doc_type TEXT, ref_doc_number TEXT, ref_doc_type2 TEXT, ref_doc_number2 TEXT
);

-- FSMA 204 Critical Tracking Event: SHIPPING (FDA template, 36 columns)
CREATE TABLE shipping_events (
  id INTEGER PRIMARY KEY,
  case_id TEXT,                                 -- the receiving record the shipment is linked to
  confirm_case_id TEXT,                         -- the shipping case where it was checked and signed
  tlc TEXT, quantity TEXT, unit_of_measure TEXT,
  product_name TEXT, brand_name TEXT, commodity TEXT, variety TEXT, packaging_size TEXT, packaging_style TEXT,
  recipient_name TEXT, recipient_phone TEXT, recipient_street TEXT, recipient_city TEXT, recipient_state TEXT, recipient_zip TEXT, recipient_country TEXT,
  shipped_from_name TEXT, shipped_from_phone TEXT, shipped_from_street TEXT, shipped_from_city TEXT, shipped_from_state TEXT, shipped_from_zip TEXT, shipped_from_country TEXT,
  ship_date TEXT,
  tlc_source_name TEXT, tlc_source_phone TEXT, tlc_source_street TEXT, tlc_source_city TEXT, tlc_source_state TEXT, tlc_source_zip TEXT, tlc_source_country TEXT,
  tlc_source_reference TEXT, ref_doc_type TEXT, ref_doc_number TEXT, ref_doc_type2 TEXT, ref_doc_number2 TEXT
);

-- Electronic signatures (receiving review, shipment confirmation, incident close)
CREATE TABLE signatures (
  id            INTEGER PRIMARY KEY,
  case_id       TEXT NOT NULL,
  step          TEXT NOT NULL CHECK (step IN ('receiving', 'shipping', 'incident')),
  signer        TEXT NOT NULL,
  signed_at     TEXT NOT NULL,
  image_file    TEXT                            -- PNG saved under backend/runtime/signatures/
);

-- Audit trail: who did what, when
CREATE TABLE audit_log (
  id            INTEGER PRIMARY KEY,
  case_id       TEXT NOT NULL,
  at            TEXT NOT NULL,
  actor         TEXT,
  action        TEXT NOT NULL
);

-- Recall: one row per customer that received the recalled lot
CREATE TABLE recall_contacts (
  id            INTEGER PRIMARY KEY,
  incident_id   TEXT NOT NULL,
  lot           TEXT NOT NULL,
  customer      TEXT NOT NULL,
  contact       TEXT,
  phone         TEXT,
  delivered     TEXT,
  invoice       TEXT,
  cases_received INTEGER,
  status        TEXT,                           -- none, notified, replied, confirmed
  overdue       INTEGER,
  calls         TEXT,                           -- JSON list of call outcomes
  reply_at      TEXT,
  destroyed     INTEGER,
  sold_before_notice INTEGER
);

-- Demo clock: the story's current time
CREATE TABLE demo_state (
  key           TEXT PRIMARY KEY,
  value         TEXT
);
