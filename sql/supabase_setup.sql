create table if not exists public.portfolio_items (
    id bigint generated always as identity primary key,
    item_type text not null check (item_type in ('project','experience','skill','education','certification','profile')),
    title text not null,
    data jsonb not null default '{}'::jsonb,
    sort_order integer not null default 0,
    published boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index if not exists portfolio_items_type_published_idx
    on public.portfolio_items (item_type, published, sort_order);
alter table public.portfolio_items enable row level security;
revoke all on public.portfolio_items from anon, authenticated;
