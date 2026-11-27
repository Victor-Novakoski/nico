-- Grupos, membros, convites e acertos (decisão 013). Dinheiro em centavos (bigint).

create table expense_group (
    id uuid primary key default gen_random_uuid(),
    name text not null check (btrim(name) <> ''),
    created_by_person_id uuid not null references person (id) on delete restrict,
    created_at timestamptz not null default now()
);

create table group_member (
    group_id uuid not null references expense_group (id) on delete cascade,
    person_id uuid not null references person (id) on delete restrict,
    role text not null check (role in ('dono', 'membro')),
    -- O que os outros membros veem dos gastos desta pessoa: só os do grupo ou todos.
    show_expenses text not null default 'grupo' check (show_expenses in ('grupo', 'todos')),
    show_income boolean not null default false,
    joined_at timestamptz not null default now(),
    primary key (group_id, person_id)
);
create index group_member_person_id_idx on group_member (person_id);

create table group_invite (
    id uuid primary key default gen_random_uuid(),
    group_id uuid not null references expense_group (id) on delete cascade,
    -- O token nunca é gravado, só o hash dele.
    token_hash text not null unique,
    expires_at timestamptz not null,
    used_at timestamptz,
    used_by_person_id uuid references person (id) on delete restrict,
    created_by_person_id uuid not null references person (id) on delete restrict,
    -- Convite usado tem data e pessoa; convite novo tem os dois nulos.
    constraint group_invite_used_both check ((used_at is null) = (used_by_person_id is null))
);
create index group_invite_group_id_idx on group_invite (group_id);

create table settlement (
    id uuid primary key default gen_random_uuid(),
    group_id uuid not null references expense_group (id) on delete cascade,
    from_person_id uuid not null references person (id) on delete restrict,
    to_person_id uuid not null references person (id) on delete restrict,
    amount_cents bigint not null check (amount_cents > 0),
    paid_on date not null,
    created_by_person_id uuid not null references person (id) on delete restrict,
    created_at timestamptz not null default now(),
    constraint settlement_from_to_differ check (from_person_id <> to_person_id)
);
create index settlement_group_id_idx on settlement (group_id);
