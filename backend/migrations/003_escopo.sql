-- Escopo dos lançamentos: pessoal (group_id nulo, de created_by_person_id) ou de um grupo.
-- A regra "compra de grupo só tem partes de membros do grupo" é garantida na API, não aqui.

alter table purchase
    add column group_id uuid references expense_group (id) on delete restrict;
create index purchase_group_id_idx on purchase (group_id);

-- Dados já existentes: com 2 ou mais pessoas nasce o grupo "Casa" com todas elas;
-- compra dividida entre mais de uma pessoa vai para o grupo, o resto fica pessoal.
do $$
declare
    owner_id uuid;
    home_id uuid;
begin
    if (select count(*) from person) < 2 then
        return;
    end if;

    select p.id into owner_id
    from person p
    left join app_user u on u.person_id = p.id
    order by (u.username is null), u.username, p.id::text
    limit 1;

    insert into expense_group (name, created_by_person_id)
    values ('Casa', owner_id)
    returning id into home_id;

    insert into group_member (group_id, person_id, role)
    select home_id, p.id, case when p.id = owner_id then 'dono' else 'membro' end
    from person p;

    update purchase
    set group_id = home_id
    where id in (
        select purchase_id from purchase_share
        group by purchase_id
        having count(distinct person_id) > 1
    );
end
$$;
