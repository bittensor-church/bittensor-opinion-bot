# bittensor-opinion-bot

Bittensor Opinion Bot

- - -

[//]: # (TODO: include bot-specific instructions and information)

## Overview

This project runs a Discord “opinion bot” backed by a Django app. The bot listens to activity in a configured Discord 
guild, stores structured events and metadata in PostgreSQL, and exposes operational/metrics data for visualization in 
Grafana. Grafana reads directly from the database; there is no custom API layer for dashboards.

It's primary responsibility is to allow:

1. In white listed discord channels
2. By users of white listed discord roles 

To post **opinions** and **upvote** them. The rules are:

1. a single opinion per channel per users (new opinion invalidates the old one)
2. a single upvote per channel per user (new upvote invalidates the old one)

This data is then accessible for easy in a public grafana instance. The value provided by it is: critical opinions
posted by important people of the ecosystem (denoted by discord roles) about specific subnets (identified 1:1 by discord
channels) are easy to view and can be upvoted by other important people.

## Observability and Grafana
- Local development: A Grafana instance is included in the local stack with a PostgreSQL data source pre-provisioned. No dashboards are provisioned — create them manually in your local Grafana.
- Staging and Production: Same approach — Grafana instances have the data source prepared, but no dashboards are provisioned. Any dashboards you create locally must be manually recreated (export/import) in these environments.
- Production Grafana usage: The production Grafana instance is for internal, development use only.
- Public dashboards: For public-facing dashboards we will use the main Grafana at bittensor.church, which will connect directly to the production PostgreSQL. There is no dashboard provisioning there either; create and manage dashboards manually.

## Basic Discord entities and minimal setup

To actually make the bot do anything, you need a few basic Discord entities configured. Minimal checklist:

- Discord Application and Bot
  - Create an application and add a Bot user in the Discord Developer Portal.
  - Copy the bot token and put it into `DISCORD_BOT_TOKEN` (in your `.env`).
- Guild (server)
  - Decide which Discord server (guild) the bot will operate in.
  - Put its numeric ID into `DISCORD_GUILD_ID` (the bot registers slash commands for this guild).
- Invite link and permissions
  - Invite the bot to the guild with scopes: `bot` and `applications.commands` (slash commands).
  - Grant at minimum these permissions in the channels where you’ll use it:
    - View Channels (Read Messages / View Channel)
    - Send Messages
    - Read Message History
    - Add Reactions
    - Use Slash Commands (Application Commands)
  - No privileged intents are required (Message Content not needed). The bot uses guild-level interactions.
- Channels
  - At least one text channel where members can run `/opinion` and the bot can read/send messages. No special channel names are required.

Quick test: in the target channel, run `/opinion` with an emoji and a short message — the bot should post it with an Upvote button.

## Required database entities (operator setup)

To make posting work in the right places, an operator must prepare a few database records via the Django Admin UI (`/admin`):

- Channel whitelist: create DiscordChannel objects from the admin panel
- Roles: create DiscordRole objects from the admin panel

# Base requirements

- docker with [compose plugin](https://docs.docker.com/compose/install/linux/)
- python 3.11
- [uv](https://docs.astral.sh/uv/)
- [nox](https://nox.thea.codes)

# Setup development environment

```sh
./setup-dev.sh
```

This creates `envs/dev/.env` from a template. Open that file and set at minimum:
```
DISCORD_BOT_TOKEN=...    # Your Discord bot token
DISCORD_GUILD_ID=...     # Numeric guild (server) ID the bot should operate in
```

```sh
docker compose up -d  # in addition to the usual stuff, this brings up Grafana at http://localhost:3000
cd app/src
uv run manage.py wait_for_database --timeout 10
uv run manage.py migrate
uv run manage.py runserver
```

# Setup production environment (git deployment)

<details>

This sets up "deployment by pushing to git storage on remote", so that:

- `git push origin ...` just pushes code to Github / other storage without any consequences;
- `git push production master` pushes code to a remote server running the app and triggers a git hook to redeploy the application.

```
Local .git ------------> Origin .git
                \
                 ------> Production .git (redeploy on push)
```

- - -

Use `ssh-keygen` to generate a key pair for the server, then add read-only access to repository in "deployment keys" section (`ssh -A` is easy to use, but not safe).

```sh
# remote server
mkdir -p ~/repos
cd ~/repos
git init --bare --initial-branch=master bittensor-opinion-bot.git

mkdir -p ~/domains/bittensor-opinion-bot
```

```sh
# locally
git remote add production root@<server>:~/repos/bittensor-opinion-bot.git
git push production master
```

```sh
# remote server
cd ~/repos/bittensor-opinion-bot.git

cat <<'EOT' > hooks/post-receive
#!/bin/bash
unset GIT_INDEX_FILE
export ROOT=/root
export REPO=bittensor-opinion-bot
while read oldrev newrev ref
do
    if [[ $ref =~ .*/master$ ]]; then
        export GIT_DIR="$ROOT/repos/$REPO.git/"
        export GIT_WORK_TREE="$ROOT/domains/$REPO/"
        git checkout -f master
        cd $GIT_WORK_TREE
        ./deploy.sh
    else
        echo "Doing nothing: only the master branch may be deployed on this server."
    fi
done
EOT

chmod +x hooks/post-receive
./hooks/post-receive
cd ~/domains/bittensor-opinion-bot
sudo bin/prepare-os.sh
./setup-prod.sh

# adjust the `.env` file

mkdir letsencrypt
./letsencrypt_setup.sh
./deploy.sh
```

### Deploy another branch

Only `master` branch is used to redeploy an application.
If one wants to deploy other branch, force may be used to push desired branch to remote's `master`:

```sh
git push --force production local-branch-to-deploy:master
```

</details>


# Background tasks with Celery

## Dead letter queue

<details>
There is a special queue named `dead_letter` that is used to store tasks
that failed for some reason.

A task should be annotated with `on_failure=send_to_dead_letter_queue`.
Once the reason of tasks failure is fixed, the task can be re-processed
by moving tasks from dead letter queue to the main one ("celery"):

    manage.py move_tasks "dead_letter" "celery"

If tasks fails again, it will be put back to dead letter queue.

To flush add tasks in specific queue, use

    manage.py flush_tasks "dead_letter"
</details>

# Monitoring

Running the app requires proper certificates to be put into `nginx/monitoring_certs`,
see [nginx/monitoring_certs/README.md](nginx/monitoring_certs/README.md) for more details.

## Monitoring execution time of code blocks

Somewhere, probably in `metrics.py`:

```python
some_calculation_time = prometheus_client.Histogram(
    'some_calculation_time',
    'How Long it took to calculate something',
    namespace='django',
    unit='seconds',
    labelnames=['task_type_for_example'],
    buckets=[0.5, 1, *range(2, 30, 2), *range(30, 75, 5), *range(75, 135, 15)]
)
```

Somewhere else:

```python
with some_calculation_time.labels('blabla').time():
    do_some_work()
```


# Cloud deployment

## AWS

<details>
Initiate the infrastructure with Terraform:
TODO

To push a new version of the application to AWS, just push to a branch named `deploy-$(ENVIRONMENT_NAME)`.
Typical values for `$(ENVIRONMENT_NAME)` are `prod` and `staging`.
For this to work, GitHub actions needs to be provided with credentials for an account that has the following policies enabled:

- AutoScalingFullAccess
- AmazonEC2ContainerRegistryFullAccess
- AmazonS3FullAccess

See `.github/workflows/cd.yml` to find out the secret names.

For more details see [README_AWS.md](README_AWS.md)
</details>

## Vultr

<details>
Initiate the infrastructure with Terraform and cloud-init:

- see Terraform template in `<project>/devops/vultr_tf/core/`
- see scripts for interacting with Vultr API in `<project>/devops/vultr_scripts/`
  - note these scripts need `vultr-cli` installed

For more details see [README_vultr.md](README_vultr.md).
</details>

# Backups

<details>
<summary>Click to for backup setup & recovery information</summary>

Backups are managed by `backups` container.

## Local volume

By default, backups will be created [periodically](backups/backup.cron) and stored in `backups` volume.

### Backups rotation
Set env var:
- `BACKUP_LOCAL_ROTATE_KEEP_LAST`

### Email

Local backups may be sent to email manually. Set env vars:
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `DEFAULT_FROM_EMAIL`

Then run:
```sh
docker compose run --rm -e EMAIL_TARGET=youremail@domain.com backups ./backup-db.sh
```

## B2 cloud storage

> In these examples we assume that backups will be stored inside `folder`. If you want to store backups in the root folder, just use empty string instead of `folder`.

First, create a Backblaze B2 account and a bucket for backups (with [lifecycle rules](https://www.backblaze.com/docs/cloud-storage-configure-and-manage-lifecycle-rules)):

```sh
b2 bucket create --lifecycle-rule '{"daysFromHidingToDeleting": 30, "daysFromUploadingToHiding": 30, "fileNamePrefix": "folder/"}' "bittensor-opinion-bot-backups" allPrivate
```

> If you want to add backups to already existing bucket, use `b2 bucket update` command and don't forget to list all previous lifecycle rules as well as adding the new one.

Create an application key with restricted access to a single bucket:

```sh
b2 key create --bucket "bittensor-opinion-bot-backups" --namePrefix "folder/" "bittensor-opinion-bot-backups-key" listBuckets,listFiles,readFiles,writeFiles
```

Fill in `.env` file:
- `BACKUP_B2_BUCKET=bittensor-opinion-bot-backups`
- `BACKUP_B2_FOLDER=folder`
- `BACKUP_B2_APPLICATION_KEY_ID=0012345abcdefgh0000000000`
- `BACKUP_B2_APPLICATION_KEY=A001bcdefgHIJKLMNOPQRSTUxx11x22`

## List all available backups

```sh
docker compose run --rm backups ./list-backups.sh
```

## Restoring system from backup after a catastrophical failure

1. Follow the instructions above to set up a new production environment
2. Restore the database using one of
```sh
docker compose run --rm backups ./restore-db.sh /var/backups/{backup-name}.dump.zstd

docker compose run --rm backups ./restore-db.sh b2://{bucket-name}/{backup-name}.dump.zstd
docker compose run --rm backups ./restore-db.sh b2id://{ID}
```
3. See if everything works
4. Make sure everything is filled up in `.env`, error reporting integration, email accounts etc

## Monitoring

`backups` container runs a simple server which [exposes essential metrics about backups](backups/bin/serve_metrics.py).

</details>

# cookiecutter-rt-django

Skeleton of this project was generated using [cookiecutter-rt-django](https://github.com/reef-technologies/cookiecutter-rt-django).
Use `cruft update` to update the project to the latest version of the template with all current bugfixes and [features](https://github.com/reef-technologies/cookiecutter-rt-django/blob/master/features.md).
