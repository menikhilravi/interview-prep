-- Prep log sync — run once in the Supabase SQL editor.
--
-- SAFE TO RUN IN A PROJECT THAT ALREADY DOES SOMETHING ELSE. Every statement
-- below names public.prep_state explicitly; nothing here alters another table,
-- another policy, or any auth setting. Row-level security scopes the rows to
-- the signed-in user, so this table cannot see or be seen by other app data.
--
-- Security model: the anon key in the app is public by design. Protection comes
-- from auth + the policies below, which make the database itself refuse to
-- return anyone's rows but your own. There is no secret to keep.

create table if not exists public.prep_state (
  user_id    uuid        not null references auth.users(id) on delete cascade,
  doc        text        not null,
  data       jsonb       not null,
  updated_at timestamptz not null default now(),
  primary key (user_id, doc),
  constraint prep_state_doc_known check (doc in ('progress','queue','banks','plan'))
);

alter table public.prep_state enable row level security;

-- Four explicit policies rather than one "for all": a mistake in a broad policy
-- fails open, and this table holds months of work.
drop policy if exists prep_state_select on public.prep_state;
drop policy if exists prep_state_insert on public.prep_state;
drop policy if exists prep_state_update on public.prep_state;
drop policy if exists prep_state_delete on public.prep_state;

create policy prep_state_select on public.prep_state
  for select using (auth.uid() = user_id);
create policy prep_state_insert on public.prep_state
  for insert with check (auth.uid() = user_id);
create policy prep_state_update on public.prep_state
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy prep_state_delete on public.prep_state
  for delete using (auth.uid() = user_id);

-- Anonymous callers get nothing; only a signed-in user acting as themselves.
revoke all on public.prep_state from anon;
grant select, insert, update, delete on public.prep_state to authenticated;


-- ── VERIFY ──────────────────────────────────────────────────────────────────
-- Run this after the above. Expect: rls_enabled = true, and 4 policy rows.
select relrowsecurity as rls_enabled
  from pg_class where oid = 'public.prep_state'::regclass;

select policyname, cmd
  from pg_policies
 where schemaname = 'public' and tablename = 'prep_state'
 order by policyname;
