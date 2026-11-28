-- Apelido de meio de pagamento é único por dono, não no banco todo (decisão 013).
-- Antes, duas pessoas não podiam usar o mesmo apelido ("nubank") e o 409 revelava
-- que outra pessoa já usava aquele apelido.
-- O dono do apelido fica gravado e a chave composta garante que é o dono do meio.

alter table payment_method
    add constraint payment_method_id_owner_key unique (id, owner_person_id);

alter table payment_method_alias add column owner_person_id uuid;

update payment_method_alias a
set owner_person_id = pm.owner_person_id
from payment_method pm
where pm.id = a.payment_method_id;

alter table payment_method_alias
    alter column owner_person_id set not null,
    add constraint payment_method_alias_method_owner_fkey
        foreign key (payment_method_id, owner_person_id)
        references payment_method (id, owner_person_id)
        on update cascade on delete cascade;

drop index payment_method_alias_alias_key;
create unique index payment_method_alias_owner_alias_key
    on payment_method_alias (owner_person_id, lower(alias));
