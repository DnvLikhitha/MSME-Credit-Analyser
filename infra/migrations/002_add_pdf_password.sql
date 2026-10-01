-- Migration 002: Add pdf_password column to documents table
-- This column stores the user-supplied password for encrypted PDF files (e.g. bank statements).
-- It is cleared (set to NULL) immediately after successful text extraction.

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS pdf_password VARCHAR(255) NULL;
