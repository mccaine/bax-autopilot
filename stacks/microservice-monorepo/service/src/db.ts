import pkg from "pg";

const { Pool } = pkg;

// Single shared connection pool. Route modules import this rather than creating
// their own Pool, so they never need to edit index.ts.
export const pool = new Pool({ connectionString: process.env.DATABASE_URL });
