-- Enable pgvector extension
create extension if not exists vector;

-- Documents table
CREATE TABLE IF NOT EXISTS documents (
    id                        uuid primary key default gen_random_uuid(),
    title                     text not null,
    content                   text,
    source_type               text not null,
    author                    text,
    created_at                timestamptz,
    last_modified             timestamptz,
    review_status             text,
    authority_score           float,
    url                       text,
    metaculus_question_id     int,
    metaculus_resolution      text,
    metaculus_resolution_date timestamptz
);

-- Chunks table
CREATE TABLE IF NOT EXISTS chunks (
    id              uuid primary key default gen_random_uuid(),
    document_id     uuid references documents(id) on delete cascade,
    content         text not null,
    embedding       vector(384),
    chunk_index     int,
    retrieval_count int default 0,
    flagged         boolean default false,
    flag_reason     text,
    decay_score     float default 1.0,
    created_at      timestamptz default now()
);

-- Quarantine queue
CREATE TABLE IF NOT EXISTS quarantine_queue (
    id                uuid primary key default gen_random_uuid(),
    chunk_id          uuid references chunks(id),
    conflict_chunk_id uuid references chunks(id),
    similarity        float,
    reason            text,
    status            text default 'pending',
    created_at        timestamptz default now(),
    reviewed_at       timestamptz
);

-- Retrieval log
CREATE TABLE IF NOT EXISTS retrieval_log (
    id           uuid primary key default gen_random_uuid(),
    query        text,
    chunk_ids    uuid[],
    retrieved_at timestamptz default now(),
    feedback     text
);

-- Indexes
create index if not exists chunks_document_id_idx on chunks(document_id);
create index if not exists chunks_flagged_idx on chunks(flagged);
create index if not exists quarantine_queue_status_idx on quarantine_queue(status);
create index if not exists retrieval_log_retrieved_at_idx on retrieval_log(retrieved_at);

-- RLS (permissive for anon key usage)
alter table documents enable row level security;
alter table chunks enable row level security;
alter table quarantine_queue enable row level security;
alter table retrieval_log enable row level security;

create policy "Allow all" on documents for all using (true);
create policy "Allow all" on chunks for all using (true);
create policy "Allow all" on quarantine_queue for all using (true);
create policy "Allow all" on retrieval_log for all using (true);

-- pgvector similarity search functions

-- Used by retrieval.py: returns top-K chunks by cosine similarity
create or replace function search_chunks(
    query_embedding vector(384),
    match_count int default 10
)
returns table (
    id uuid,
    document_id uuid,
    content text,
    similarity float,
    decay_score float,
    flagged boolean,
    retrieval_count int
)
language sql stable
as $$
    select
        c.id,
        c.document_id,
        c.content,
        1 - (c.embedding <=> query_embedding) as similarity,
        c.decay_score,
        c.flagged,
        c.retrieval_count
    from chunks c
    where c.embedding is not null
    order by c.embedding <=> query_embedding
    limit match_count;
$$;

-- Used by ingestion.py: find similar chunks from OTHER documents
create or replace function find_similar_chunks(
    query_embedding vector(384),
    match_threshold float default 0.88,
    match_count int default 5,
    exclude_document_id uuid default null
)
returns table (
    id uuid,
    document_id uuid,
    similarity float
)
language sql stable
as $$
    select
        c.id,
        c.document_id,
        1 - (c.embedding <=> query_embedding) as similarity
    from chunks c
    where
        c.embedding is not null
        and (exclude_document_id is null or c.document_id != exclude_document_id)
        and 1 - (c.embedding <=> query_embedding) >= match_threshold
    order by c.embedding <=> query_embedding
    limit match_count;
$$;
