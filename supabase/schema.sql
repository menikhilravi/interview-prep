-- Prep log sync — run once in the Supabase SQL editor.
--
-- Security model: the anon key in the app is public by design. Protection comes
-- from auth + row-level security below, which makes the database itself refuse
-- to return anyone's rows but your own. There is no secret to keep.

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
-- fails open, and this table is the only copy of months of work.
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

-- Sanity check after running this — should print rowsecurity = true and 4 policies.
-- select relrowsecurity from pg_class where oid = 'public.prep_state'::regclass;
-- select policyname from pg_policies where tablename = 'prep_state';
