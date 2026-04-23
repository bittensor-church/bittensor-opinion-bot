from os import environ

from django.db import migrations


def set_readonly_permissions(_apps, schema_editor):
    user = environ["POSTGRES_READONLY_USER"]
    password = environ["POSTGRES_READONLY_PASSWORD"]

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            DO $$
            BEGIN
              IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = %(user)s) THEN
                EXECUTE 'CREATE ROLE '
                  || quote_ident(%(user)s)
                  || ' WITH LOGIN PASSWORD '
                  || quote_literal(%(password)s);
              END IF;
              EXECUTE 'GRANT CONNECT ON DATABASE '
                || quote_ident(current_database())
                || ' TO '
                || quote_ident(%(user)s);
              EXECUTE 'GRANT USAGE ON SCHEMA public TO ' || quote_ident(%(user)s);
              IF to_regclass('public.opinion_bot_opinion') IS NOT NULL THEN
                EXECUTE 'GRANT SELECT ON TABLE public.opinion_bot_opinion TO ' || quote_ident(%(user)s);
              END IF;
              IF to_regclass('public.opinion_bot_upvote') IS NOT NULL THEN
                EXECUTE 'GRANT SELECT ON TABLE public.opinion_bot_upvote TO ' || quote_ident(%(user)s);
              END IF;
            END
            $$;
            """,
            {"user": user, "password": password},
        )


def unset_readonly_permissions(_apps, schema_editor):
    user = environ["POSTGRES_READONLY_USER"]

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            DO $$
            BEGIN
              IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = %(user)s) THEN
                EXECUTE 'REVOKE SELECT ON TABLE public.opinion_bot_opinion FROM ' || quote_ident(%(user)s);
                EXECUTE 'REVOKE SELECT ON TABLE public.opinion_bot_upvote FROM ' || quote_ident(%(user)s);
                EXECUTE 'REVOKE USAGE ON SCHEMA public FROM ' || quote_ident(%(user)s);
                EXECUTE 'REVOKE CONNECT ON DATABASE '
                  || quote_ident(current_database())
                  || ' FROM '
                  || quote_ident(%(user)s);
                EXECUTE 'DROP ROLE ' || quote_ident(%(user)s);
              END IF;
            END
            $$;
            """,
            {"user": user},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("opinion_bot", "0011_alter_subnetinstance_name"),
    ]

    operations = [
        migrations.RunPython(set_readonly_permissions, unset_readonly_permissions),
    ]
