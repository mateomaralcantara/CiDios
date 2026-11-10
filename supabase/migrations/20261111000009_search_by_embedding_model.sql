-- La búsqueda semántica solo compara vectores calculados con el MISMO modelo de embeddings
-- (local «hashing-lexical-v1» o Gemini). Permite migrar de modelo sin mezclar espacios vectoriales.
drop function if exists public.hybrid_search(text, vector, int, text);

create or replace function public.hybrid_search(
  query_text text,
  query_embedding vector(384),
  match_count int default 10,
  mode text default 'hybrid',          -- 'text' | 'semantic' | 'hybrid'
  embedding_model text default null    -- null = cualquier modelo (compatibilidad)
) returns table (
  chunk_id uuid, document_id uuid, document_title text, locator text, content text,
  text_rank real, semantic_score real, score real, injection_risk boolean
)
language sql stable security invoker set search_path = public, extensions, pg_temp as $$
  with q as (
    select coalesce(nullif(replace(websearch_to_tsquery('public.es_unaccent', query_text)::text, ' & ', ' | '), ''), '''''')::tsquery as tsq
  ),
  t as (
    select c.id, ts_rank_cd(c.content_tsv, q.tsq) as r,
           row_number() over (order by ts_rank_cd(c.content_tsv, q.tsq) desc) as rn
    from public.document_chunks c, q
    where mode in ('text','hybrid') and c.content_tsv @@ q.tsq
    order by r desc limit greatest(match_count * 4, 20)
  ),
  s as (
    select c.id, 1 - (c.embedding <=> query_embedding) as sim,
           row_number() over (order by c.embedding <=> query_embedding) as rn
    from public.document_chunks c
    where mode in ('semantic','hybrid') and query_embedding is not null and c.embedding is not null
      and (hybrid_search.embedding_model is null or c.embedding_model = hybrid_search.embedding_model)
      and 1 - (c.embedding <=> query_embedding) >= 0.1
    order by c.embedding <=> query_embedding limit greatest(match_count * 4, 20)
  ),
  fused as (
    select coalesce(t.id, s.id) as id,
           coalesce(t.r, 0)::real as text_rank,
           coalesce(s.sim, 0)::real as semantic_score,
           (coalesce(1.0 / (60 + t.rn), 0) + coalesce(1.0 / (60 + s.rn), 0))::real as score
    from t full outer join s on t.id = s.id
  )
  select c.id, d.id, d.title, c.locator, c.content, f.text_rank, f.semantic_score, f.score, c.injection_risk
  from fused f
  join public.document_chunks c on c.id = f.id
  join public.documents d on d.id = c.document_id
  order by f.score desc
  limit match_count
$$;

grant execute on function public.hybrid_search(text, vector, int, text, text) to anon, authenticated;
comment on function public.hybrid_search(text, vector, int, text, text) is 'Búsqueda textual, semántica o híbrida sobre la biblioteca (respeta RLS). Llamable por RPC.';
create index if not exists document_chunks_embedding_model_idx on public.document_chunks (embedding_model);
