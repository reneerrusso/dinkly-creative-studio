-- DINKLY Creative Studio cloud persistence v1
-- Apply with scripts/apply_migrations.py using the direct DATABASE_URL.

create extension if not exists pgcrypto;

create table if not exists schema_migrations (
  version text primary key,
  applied_at timestamptz not null default now()
);

create table if not exists runtime_documents (
  key text primary key,
  value_json jsonb not null,
  version bigint not null default 1,
  updated_at timestamptz not null default now()
);

create table if not exists agent_memories (
  id text primary key,
  memory_type text not null,
  key text not null,
  summary text not null,
  value_json jsonb not null default '{}'::jsonb,
  confidence text not null check (confidence in ('high','medium','low')),
  source_type text not null,
  source_id text,
  evidence_ids jsonb not null default '[]'::jsonb,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(memory_type, key)
);

create table if not exists creative_preferences (
  id text primary key,
  topic text not null,
  direction text not null,
  statement text not null,
  evidence_ids jsonb not null default '[]'::jsonb,
  confidence text not null default 'high',
  active boolean not null default true,
  source_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists used_storylines (
  id text primary key,
  title text,
  storyline text not null,
  generation_id text,
  date_used timestamptz,
  record_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists prompt_learnings (
  id text primary key,
  statement text not null,
  evidence_ids jsonb not null default '[]'::jsonb,
  confidence text not null,
  active boolean not null default true,
  record_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  last_validated_at timestamptz,
  updated_at timestamptz not null default now()
);

create table if not exists qa_learnings (like prompt_learnings including all);
create table if not exists generation_learnings (like prompt_learnings including all);

create table if not exists failure_patterns (
  id text primary key,
  failure text not null,
  evidence_ids jsonb not null default '[]'::jsonb,
  occurrence_count integer not null default 1,
  confidence text not null,
  active boolean not null default true,
  record_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  last_validated_at timestamptz,
  updated_at timestamptz not null default now()
);

create table if not exists concept_feedback (
  id text primary key,
  concept_id text,
  generation_id text,
  feedback text not null,
  sentiment text,
  channel text not null,
  user_id text,
  created_at timestamptz not null default now()
);

create table if not exists conversation_threads (
  id text primary key,
  channel text not null check (channel in ('web','slack')),
  external_thread_id text not null,
  user_id text,
  last_active_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  unique(channel, external_thread_id)
);

create table if not exists conversation_messages (
  id text primary key,
  thread_id text not null references conversation_threads(id) on delete cascade,
  role text not null,
  content text not null,
  external_message_id text,
  linked_task_ids jsonb not null default '[]'::jsonb,
  linked_generation_ids jsonb not null default '[]'::jsonb,
  record_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists agent_tasks (
  id text primary key,
  source_channel text not null,
  source_thread_id text not null,
  instruction text not null,
  task_type text not null,
  status text not null,
  priority integer not null default 6,
  context_json jsonb not null default '{}'::jsonb,
  requires_approval boolean not null default false,
  dedupe_key text unique,
  record_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz,
  failed_at timestamptz,
  updated_at timestamptz not null default now()
);

create index if not exists idx_agent_tasks_queue on agent_tasks(status, priority, created_at);
create index if not exists idx_agent_tasks_thread on agent_tasks(source_thread_id, created_at desc);

create table if not exists agent_events (
  id text primary key,
  task_id text,
  generation_id text,
  kind text not null,
  level text not null default 'info',
  message text not null,
  data_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists generation_runs (
  id text primary key,
  status text not null,
  concept_text text,
  story_format text,
  source_channel text,
  source_task_id text,
  brain_refs_used jsonb not null default '[]'::jsonb,
  memory_refs_used jsonb not null default '[]'::jsonb,
  prompt_template_version text,
  character_rule_version text,
  failure_rule_version text,
  image_model text,
  image_model_tier text,
  published_at timestamptz,
  platform text,
  post_url text,
  views bigint,
  likes bigint,
  comments bigint,
  shares bigint,
  saves bigint,
  followers_at_publish bigint,
  record_json jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists generation_candidates (
  id text primary key,
  generation_id text not null references generation_runs(id) on delete cascade,
  label text,
  model text,
  model_tier text,
  qa_status text,
  recommended boolean not null default false,
  selected boolean not null default false,
  asset_id text,
  final_asset_id text,
  record_json jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists approvals (
  id text primary key,
  item_type text not null,
  item_id text not null,
  decision text not null,
  notes text,
  channel text not null,
  user_id text,
  created_at timestamptz not null default now()
);

create table if not exists brain_update_proposals (
  id text primary key,
  title text not null,
  proposed_rule text not null,
  target_file text not null,
  evidence_ids jsonb not null default '[]'::jsonb,
  confidence text not null,
  status text not null default 'pending' check (status in ('pending','approved','rejected')),
  edited_rule text,
  record_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  reviewed_at timestamptz,
  reviewed_by text,
  application_status text not null default 'not_applied',
  applied_at timestamptz,
  applied_commit_sha text
);

create table if not exists learning_checkpoints (
  id text primary key,
  checkpoint_type text not null,
  last_processed_at timestamptz,
  seen_evidence_ids jsonb not null default '[]'::jsonb,
  pending_evidence_ids jsonb not null default '[]'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists assets (
  id text primary key,
  asset_type text not null,
  storage_bucket text not null,
  storage_path text not null unique,
  content_type text,
  sha256 text,
  size_bytes bigint,
  generation_id text,
  candidate_id text,
  metadata_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists post_performance_snapshots (
  id uuid primary key default gen_random_uuid(),
  generation_id text not null references generation_runs(id) on delete cascade,
  captured_at timestamptz not null default now(),
  views bigint,
  likes bigint,
  comments bigint,
  shares bigint,
  saves bigint
);

create table if not exists processed_channel_events (
  id text primary key,
  processed_at timestamptz not null default now()
);

create table if not exists channel_outbox (
  id text primary key,
  record_json jsonb not null,
  created_at timestamptz not null default now()
);

create table if not exists learning_cost_ledger (
  id uuid primary key default gen_random_uuid(),
  task_id text not null,
  estimated_cost numeric(12,6) not null default 0,
  reported_cost numeric(12,6),
  created_at timestamptz not null default now()
);

create or replace function persist_agent_task(p_record jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare existing agent_tasks%rowtype;
declare saved agent_tasks%rowtype;
begin
  select * into existing from agent_tasks where id = p_record->>'id' for update;
  if existing.id is not null
     and coalesce(p_record->>'status', 'queued') = 'queued'
     and existing.status <> 'queued' then
    return existing.record_json;
  end if;
  insert into agent_tasks (
    id, source_channel, source_thread_id, instruction, task_type, status, priority,
    context_json, requires_approval, dedupe_key, record_json, created_at, started_at,
    completed_at, failed_at, updated_at
  ) values (
    p_record->>'id', coalesce(p_record->>'source_channel', 'web'),
    coalesce(p_record->>'source_thread_id', 'web-default'),
    coalesce(p_record->>'user_instruction', p_record->>'instruction', 'DINKLY task'),
    coalesce(p_record->>'task_type', 'custom'), coalesce(p_record->>'status', 'queued'),
    coalesce((p_record->>'priority')::integer, 6), coalesce(p_record->'context', '{}'::jsonb),
    coalesce((p_record->>'approval_required')::boolean, false), p_record->>'dedupe_key', p_record,
    coalesce((p_record->>'created_at')::timestamptz, now()),
    (p_record->>'started_at')::timestamptz, (p_record->>'completed_at')::timestamptz,
    coalesce((p_record->>'failed_at')::timestamptz,
      case when p_record->>'status' = 'failed' then (p_record->>'completed_at')::timestamptz end), now()
  )
  on conflict (id) do update set
    source_channel = excluded.source_channel,
    source_thread_id = excluded.source_thread_id,
    instruction = excluded.instruction,
    task_type = excluded.task_type,
    status = excluded.status,
    priority = excluded.priority,
    context_json = excluded.context_json,
    requires_approval = excluded.requires_approval,
    dedupe_key = excluded.dedupe_key,
    record_json = excluded.record_json,
    started_at = excluded.started_at,
    completed_at = excluded.completed_at,
    failed_at = excluded.failed_at,
    updated_at = now()
  returning * into saved;
  return saved.record_json;
end;
$$;

create or replace function mark_processed_channel_event(p_id text)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare inserted_count integer;
begin
  insert into processed_channel_events(id) values (p_id) on conflict do nothing;
  get diagnostics inserted_count = row_count;
  return inserted_count = 1;
end;
$$;

create or replace function claim_next_agent_task()
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare selected agent_tasks%rowtype;
begin
  select * into selected
  from agent_tasks
  where status = 'queued'
    and coalesce((context_json->>'slack_ack_pending')::boolean, false) = false
  order by priority asc, created_at asc
  for update skip locked
  limit 1;
  if selected.id is null then return null; end if;
  update agent_tasks
  set status = 'running', started_at = now(), updated_at = now(),
      record_json = jsonb_set(jsonb_set(selected.record_json, '{status}', '"running"'::jsonb), '{started_at}', to_jsonb(now()))
  where id = selected.id
  returning * into selected;
  return selected.record_json;
end;
$$;

-- Security-definer queue helpers are backend-only. Supabase's service role is
-- used by the FastAPI runtime; browser-facing roles cannot execute them.
revoke execute on function persist_agent_task(jsonb) from public, anon, authenticated;
revoke execute on function mark_processed_channel_event(text) from public, anon, authenticated;
revoke execute on function claim_next_agent_task() from public, anon, authenticated;
grant execute on function persist_agent_task(jsonb) to service_role;
grant execute on function mark_processed_channel_event(text) to service_role;
grant execute on function claim_next_agent_task() to service_role;

alter table agent_memories enable row level security;
alter table creative_preferences enable row level security;
alter table generation_runs enable row level security;
alter table generation_candidates enable row level security;
alter table conversation_threads enable row level security;
alter table conversation_messages enable row level security;
-- No public policies are created. The backend service role is the only v1 data client.

insert into schema_migrations(version) values ('0001_dinkly_cloud') on conflict do nothing;
