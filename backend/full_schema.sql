          List of schemas
      Name      |       Owner       
----------------+-------------------
 auth           | supabase_admin
 extensions     | postgres
 graphql        | supabase_admin
 graphql_public | supabase_admin
 pgbouncer      | pgbouncer
 public         | pg_database_owner
 realtime       | supabase_admin
 storage        | supabase_admin
 vault          | supabase_admin
(9 rows)

                                                           Table "public.accounts"
      Column      |           Type           | Collation | Nullable |      Default      | Storage  | Compression | Stats target | Description 
------------------+--------------------------+-----------+----------+-------------------+----------+-------------+--------------+-------------
 id               | uuid                     |           | not null | gen_random_uuid() | plain    |             |              | 
 google_email     | text                     |           | not null |                   | extended |             |              | 
 created_at       | timestamp with time zone |           |          | now()             | plain    |             |              | 
 updated_at       | timestamp with time zone |           |          | now()             | plain    |             |              | 
 data_initialized | boolean                  |           |          | false             | plain    |             |              | 
 user_id          | uuid                     |           |          |                   | plain    |             |              | 
Indexes:
    "accounts_pkey" PRIMARY KEY, btree (id)
    "accounts_google_email_key" UNIQUE CONSTRAINT, btree (google_email)
Foreign-key constraints:
    "accounts_user_id_fkey" FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE
Referenced by:
    TABLE "alert_deliveries" CONSTRAINT "alert_deliveries_account_id_fkey" FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
    TABLE "alert_recipients" CONSTRAINT "alert_recipients_account_id_fkey" FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
    TABLE "alert_subscriptions" CONSTRAINT "alert_subscriptions_account_id_fkey" FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
    TABLE "alerts" CONSTRAINT "alerts_account_id_fkey" FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
    TABLE "gsc_tokens" CONSTRAINT "gsc_tokens_account_id_fkey" FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
    TABLE "pipeline_runs" CONSTRAINT "pipeline_runs_account_id_fkey" FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
    TABLE "properties" CONSTRAINT "properties_account_id_fkey" FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
    TABLE "websites" CONSTRAINT "websites_account_id_fkey" FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
Access method: heap

              Index "public.accounts_google_email_key"
    Column    | Type | Key? |  Definition  | Storage  | Stats target 
--------------+------+------+--------------+----------+--------------
 google_email | text | yes  | google_email | extended | 
unique, btree, for table "public.accounts"

                Index "public.accounts_pkey"
 Column | Type | Key? | Definition | Storage | Stats target 
--------+------+------+------------+---------+--------------
 id     | uuid | yes  | id         | plain   | 
primary key, btree, for table "public.accounts"

                                                    Table "public.alert_deliveries"
   Column   |           Type           | Collation | Nullable |      Default      | Storage  | Compression | Stats target | Description 
------------+--------------------------+-----------+----------+-------------------+----------+-------------+--------------+-------------
 id         | uuid                     |           | not null | gen_random_uuid() | plain    |             |              | 
 alert_id   | uuid                     |           | not null |                   | plain    |             |              | 
 account_id | uuid                     |           | not null |                   | plain    |             |              | 
 email      | text                     |           | not null |                   | extended |             |              | 
 sent       | boolean                  |           |          | false             | plain    |             |              | 
 sent_at    | timestamp with time zone |           |          |                   | plain    |             |              | 
 created_at | timestamp with time zone |           |          | now()             | plain    |             |              | 
 suppressed | boolean                  |           | not null | false             | plain    |             |              | 
Indexes:
    "alert_deliveries_pkey" PRIMARY KEY, btree (id)
    "alert_deliveries_alert_id_email_key" UNIQUE CONSTRAINT, btree (alert_id, email)
    "idx_alert_deliveries_alert_unsent" btree (alert_id) WHERE sent = false
    "idx_alert_deliveries_cooldown" btree (email, sent_at) WHERE sent = true AND suppressed = false
Foreign-key constraints:
    "alert_deliveries_account_id_fkey" FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
    "alert_deliveries_alert_id_fkey" FOREIGN KEY (alert_id) REFERENCES alerts(id) ON DELETE CASCADE
Access method: heap

      Index "public.alert_deliveries_alert_id_email_key"
  Column  | Type | Key? | Definition | Storage  | Stats target 
----------+------+------+------------+----------+--------------
 alert_id | uuid | yes  | alert_id   | plain    | 
 email    | text | yes  | email      | extended | 
unique, btree, for table "public.alert_deliveries"

            Index "public.alert_deliveries_pkey"
 Column | Type | Key? | Definition | Storage | Stats target 
--------+------+------+------------+---------+--------------
 id     | uuid | yes  | id         | plain   | 
primary key, btree, for table "public.alert_deliveries"

                                                    Table "public.alert_recipients"
   Column   |           Type           | Collation | Nullable |      Default      | Storage  | Compression | Stats target | Description 
------------+--------------------------+-----------+----------+-------------------+----------+-------------+--------------+-------------
 id         | uuid                     |           | not null | gen_random_uuid() | plain    |             |              | 
 email      | text                     |           | not null |                   | extended |             |              | 
 created_at | timestamp with time zone |           |          | now()             | plain    |             |              | 
 account_id | uuid                     |           | not null |                   | plain    |             |              | 
Indexes:
    "alert_recipients_pkey" PRIMARY KEY, btree (id)
    "alert_recipients_account_email_unique" UNIQUE CONSTRAINT, btree (account_id, email)
    "recipients_account_email_unique" UNIQUE, btree (account_id, email)
    "unique_alert_recipient" UNIQUE CONSTRAINT, btree (account_id, email)
Foreign-key constraints:
    "alert_recipients_account_id_fkey" FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
Access method: heap

      Index "public.alert_recipients_account_email_unique"
   Column   | Type | Key? | Definition | Storage  | Stats target 
------------+------+------+------------+----------+--------------
 account_id | uuid | yes  | account_id | plain    | 
 email      | text | yes  | email      | extended | 
unique, btree, for table "public.alert_recipients"

            Index "public.alert_recipients_pkey"
 Column | Type | Key? | Definition | Storage | Stats target 
--------+------+------+------------+---------+--------------
 id     | uuid | yes  | id         | plain   | 
primary key, btree, for table "public.alert_recipients"

                                                   Table "public.alert_subscriptions"
   Column    |           Type           | Collation | Nullable |      Default      | Storage  | Compression | Stats target | Description 
-------------+--------------------------+-----------+----------+-------------------+----------+-------------+--------------+-------------
 id          | uuid                     |           | not null | gen_random_uuid() | plain    |             |              | 
 account_id  | uuid                     |           | not null |                   | plain    |             |              | 
 email       | text                     |           | not null |                   | extended |             |              | 
 property_id | uuid                     |           | not null |                   | plain    |             |              | 
 created_at  | timestamp with time zone |           |          | now()             | plain    |             |              | 
Indexes:
    "alert_subscriptions_pkey" PRIMARY KEY, btree (id)
    "alert_subscriptions_account_id_email_property_id_key" UNIQUE CONSTRAINT, btree (account_id, email, property_id)
    "unique_alert_subscription" UNIQUE CONSTRAINT, btree (account_id, email, property_id)
Foreign-key constraints:
    "alert_subscriptions_account_id_fkey" FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
    "alert_subscriptions_property_id_fkey" FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
Access method: heap

Index "public.alert_subscriptions_account_id_email_property_id_key"
   Column    | Type | Key? | Definition  | Storage  | Stats target 
-------------+------+------+-------------+----------+--------------
 account_id  | uuid | yes  | account_id  | plain    | 
 email       | text | yes  | email       | extended | 
 property_id | uuid | yes  | property_id | plain    | 
unique, btree, for table "public.alert_subscriptions"

          Index "public.alert_subscriptions_pkey"
 Column | Type | Key? | Definition | Storage | Stats target 
--------+------+------+------------+---------+--------------
 id     | uuid | yes  | id         | plain   | 
primary key, btree, for table "public.alert_subscriptions"

                                                             Table "public.alerts"
       Column       |           Type           | Collation | Nullable |      Default      | Storage  | Compression | Stats target | Description 
--------------------+--------------------------+-----------+----------+-------------------+----------+-------------+--------------+-------------
 id                 | uuid                     |           | not null | gen_random_uuid() | plain    |             |              | 
 property_id        | uuid                     |           | not null |                   | plain    |             |              | 
 alert_type         | text                     |           | not null |                   | extended |             |              | 
 prev_7_impressions | integer                  |           | not null |                   | plain    |             |              | 
 last_7_impressions | integer                  |           | not null |                   | plain    |             |              | 
 delta_pct          | numeric(10,2)            |           | not null |                   | main     |             |              | 
 triggered_at       | timestamp with time zone |           |          | now()             | plain    |             |              | 
 email_sent         | boolean                  |           |          | false             | plain    |             |              | 
 account_id         | uuid                     |           | not null |                   | plain    |             |              | 
Indexes:
    "alerts_pkey" PRIMARY KEY, btree (id)
    "idx_alerts_account" btree (account_id)
    "idx_alerts_account_triggered" btree (account_id, triggered_at DESC)
    "idx_alerts_dedup" btree (account_id, property_id, alert_type, triggered_at DESC)
Foreign-key constraints:
    "alerts_account_id_fkey" FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
    "alerts_property_fk" FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
Referenced by:
    TABLE "alert_deliveries" CONSTRAINT "alert_deliveries_alert_id_fkey" FOREIGN KEY (alert_id) REFERENCES alerts(id) ON DELETE CASCADE
Access method: heap

                 Index "public.alerts_pkey"
 Column | Type | Key? | Definition | Storage | Stats target 
--------+------+------+------------+---------+--------------
 id     | uuid | yes  | id         | plain   | 
primary key, btree, for table "public.alerts"

                                                    Table "public.device_daily_metrics"
   Column    |            Type             | Collation | Nullable |      Default      | Storage  | Compression | Stats target | Description 
-------------+-----------------------------+-----------+----------+-------------------+----------+-------------+--------------+-------------
 id          | uuid                        |           | not null | gen_random_uuid() | plain    |             |              | 
 property_id | uuid                        |           | not null |                   | plain    |             |              | 
 device      | text                        |           | not null |                   | extended |             |              | 
 date        | date                        |           | not null |                   | plain    |             |              | 
 clicks      | integer                     |           | not null |                   | plain    |             |              | 
 impressions | integer                     |           | not null |                   | plain    |             |              | 
 ctr         | numeric(10,6)               |           | not null |                   | main     |             |              | 
 position    | numeric(10,2)               |           | not null |                   | main     |             |              | 
 created_at  | timestamp without time zone |           |          | now()             | plain    |             |              | 
 updated_at  | timestamp without time zone |           |          | now()             | plain    |             |              | 
Indexes:
    "device_daily_metrics_pkey" PRIMARY KEY, btree (id)
    "device_daily_metrics_property_id_device_date_key" UNIQUE CONSTRAINT, btree (property_id, device, date)
    "idx_device_metrics_property_date" btree (property_id, date DESC)
    "idx_device_metrics_property_device" btree (property_id, device)
    "idx_device_property_date" btree (property_id, date)
    "idx_device_property_device_date" btree (property_id, device, date)
    "unique_device_metric" UNIQUE CONSTRAINT, btree (property_id, device, date)
Check constraints:
    "device_daily_metrics_device_check" CHECK (device = ANY (ARRAY['desktop'::text, 'mobile'::text, 'tablet'::text]))
Foreign-key constraints:
    "device_daily_metrics_property_id_fkey" FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
Access method: heap

          Index "public.device_daily_metrics_pkey"
 Column | Type | Key? | Definition | Storage | Stats target 
--------+------+------+------------+---------+--------------
 id     | uuid | yes  | id         | plain   | 
primary key, btree, for table "public.device_daily_metrics"

  Index "public.device_daily_metrics_property_id_device_date_key"
   Column    | Type | Key? | Definition  | Storage  | Stats target 
-------------+------+------+-------------+----------+--------------
 property_id | uuid | yes  | property_id | plain    | 
 device      | text | yes  | device      | extended | 
 date        | date | yes  | date        | plain    | 
unique, btree, for table "public.device_daily_metrics"

                                                                      Table "public.gsc_tokens"
    Column     |           Type           | Collation | Nullable |                   Default                   | Storage  | Compression | Stats target | Description 
---------------+--------------------------+-----------+----------+---------------------------------------------+----------+-------------+--------------+-------------
 account_id    | uuid                     |           | not null |                                             | plain    |             |              | 
 access_token  | text                     |           | not null |                                             | extended |             |              | 
 refresh_token | text                     |           | not null |                                             | extended |             |              | 
 token_uri     | text                     |           | not null | 'https://oauth2.googleapis.com/token'::text | extended |             |              | 
 client_id     | text                     |           | not null |                                             | extended |             |              | 
 client_secret | text                     |           | not null |                                             | extended |             |              | 
 scopes        | text[]                   |           |          |                                             | extended |             |              | 
 expiry        | timestamp with time zone |           |          |                                             | plain    |             |              | 
 created_at    | timestamp with time zone |           |          | now()                                       | plain    |             |              | 
 updated_at    | timestamp with time zone |           |          | now()                                       | plain    |             |              | 
Indexes:
    "gsc_tokens_pkey" PRIMARY KEY, btree (account_id)
    "gsc_tokens_account_unique" UNIQUE CONSTRAINT, btree (account_id)
Foreign-key constraints:
    "gsc_tokens_account_id_fkey" FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
Access method: heap

            Index "public.gsc_tokens_account_unique"
   Column   | Type | Key? | Definition | Storage | Stats target 
------------+------+------+------------+---------+--------------
 account_id | uuid | yes  | account_id | plain   | 
unique, btree, for table "public.gsc_tokens"

                 Index "public.gsc_tokens_pkey"
   Column   | Type | Key? | Definition | Storage | Stats target 
------------+------+------+------------+---------+--------------
 account_id | uuid | yes  | account_id | plain   | 
primary key, btree, for table "public.gsc_tokens"

       Index "public.idx_alert_deliveries_alert_unsent"
  Column  | Type | Key? | Definition | Storage | Stats target 
----------+------+------+------------+---------+--------------
 alert_id | uuid | yes  | alert_id   | plain   | 
btree, for table "public.alert_deliveries", predicate (sent = false)

                   Index "public.idx_alert_deliveries_cooldown"
 Column  |           Type           | Key? | Definition | Storage  | Stats target 
---------+--------------------------+------+------------+----------+--------------
 email   | text                     | yes  | email      | extended | 
 sent_at | timestamp with time zone | yes  | sent_at    | plain    | 
btree, for table "public.alert_deliveries", predicate (sent = true AND suppressed = false)

               Index "public.idx_alerts_account"
   Column   | Type | Key? | Definition | Storage | Stats target 
------------+------+------+------------+---------+--------------
 account_id | uuid | yes  | account_id | plain   | 
btree, for table "public.alerts"

                      Index "public.idx_alerts_account_triggered"
    Column    |           Type           | Key? |  Definition  | Storage | Stats target 
--------------+--------------------------+------+--------------+---------+--------------
 account_id   | uuid                     | yes  | account_id   | plain   | 
 triggered_at | timestamp with time zone | yes  | triggered_at | plain   | 
btree, for table "public.alerts"

                             Index "public.idx_alerts_dedup"
    Column    |           Type           | Key? |  Definition  | Storage  | Stats target 
--------------+--------------------------+------+--------------+----------+--------------
 account_id   | uuid                     | yes  | account_id   | plain    | 
 property_id  | uuid                     | yes  | property_id  | plain    | 
 alert_type   | text                     | yes  | alert_type   | extended | 
 triggered_at | timestamp with time zone | yes  | triggered_at | plain    | 
btree, for table "public.alerts"

         Index "public.idx_device_metrics_property_date"
   Column    | Type | Key? | Definition  | Storage | Stats target 
-------------+------+------+-------------+---------+--------------
 property_id | uuid | yes  | property_id | plain   | 
 date        | date | yes  | date        | plain   | 
btree, for table "public.device_daily_metrics"

         Index "public.idx_device_metrics_property_device"
   Column    | Type | Key? | Definition  | Storage  | Stats target 
-------------+------+------+-------------+----------+--------------
 property_id | uuid | yes  | property_id | plain    | 
 device      | text | yes  | device      | extended | 
btree, for table "public.device_daily_metrics"

             Index "public.idx_device_property_date"
   Column    | Type | Key? | Definition  | Storage | Stats target 
-------------+------+------+-------------+---------+--------------
 property_id | uuid | yes  | property_id | plain   | 
 date        | date | yes  | date        | plain   | 
btree, for table "public.device_daily_metrics"

          Index "public.idx_device_property_device_date"
   Column    | Type | Key? | Definition  | Storage  | Stats target 
-------------+------+------+-------------+----------+--------------
 property_id | uuid | yes  | property_id | plain    | 
 device      | text | yes  | device      | extended | 
 date        | date | yes  | date        | plain    | 
btree, for table "public.device_daily_metrics"

              Index "public.idx_page_property_date"
   Column    | Type | Key? | Definition  | Storage | Stats target 
-------------+------+------+-------------+---------+--------------
 property_id | uuid | yes  | property_id | plain   | 
 date        | date | yes  | date        | plain   | 
btree, for table "public.page_daily_metrics"

            Index "public.idx_pipeline_runs_account"
   Column   | Type | Key? | Definition | Storage | Stats target 
------------+------+------+------------+---------+--------------
 account_id | uuid | yes  | account_id | plain   | 
btree, for table "public.pipeline_runs"

             Index "public.idx_properties_account"
   Column   | Type | Key? | Definition | Storage | Stats target 
------------+------+------+------------+---------+--------------
 account_id | uuid | yes  | account_id | plain   | 
btree, for table "public.properties"

        Index "public.idx_property_metrics_property_date"
   Column    | Type | Key? | Definition  | Storage | Stats target 
-------------+------+------+-------------+---------+--------------
 property_id | uuid | yes  | property_id | plain   | 
 date        | date | yes  | date        | plain   | 
btree, for table "public.property_daily_metrics"

            Index "public.idx_property_property_date"
   Column    | Type | Key? | Definition  | Storage | Stats target 
-------------+------+------+-------------+---------+--------------
 property_id | uuid | yes  | property_id | plain   | 
 date        | date | yes  | date        | plain   | 
btree, for table "public.property_daily_metrics"

              Index "public.idx_websites_account"
   Column   | Type | Key? | Definition | Storage | Stats target 
------------+------+------+------------+---------+--------------
 account_id | uuid | yes  | account_id | plain   | 
btree, for table "public.websites"

        Index "public.one_running_pipeline_per_account"
   Column   | Type | Key? | Definition | Storage | Stats target 
------------+------+------+------------+---------+--------------
 account_id | uuid | yes  | account_id | plain   | 
unique, btree, for table "public.pipeline_runs", predicate (is_running = true)

                                                    Table "public.page_daily_metrics"
   Column    |           Type           | Collation | Nullable |      Default      | Storage  | Compression | Stats target | Description 
-------------+--------------------------+-----------+----------+-------------------+----------+-------------+--------------+-------------
 id          | uuid                     |           | not null | gen_random_uuid() | plain    |             |              | 
 property_id | uuid                     |           | not null |                   | plain    |             |              | 
 page_url    | text                     |           | not null |                   | extended |             |              | 
 date        | date                     |           | not null |                   | plain    |             |              | 
 clicks      | integer                  |           | not null | 0                 | plain    |             |              | 
 impressions | integer                  |           | not null | 0                 | plain    |             |              | 
 created_at  | timestamp with time zone |           |          | now()             | plain    |             |              | 
 updated_at  | timestamp with time zone |           |          | now()             | plain    |             |              | 
Indexes:
    "page_daily_metrics_pkey" PRIMARY KEY, btree (id)
    "idx_page_property_date" btree (property_id, date)
    "unique_page_day" UNIQUE CONSTRAINT, btree (property_id, page_url, date)
Foreign-key constraints:
    "page_daily_metrics_property_id_fkey" FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
Access method: heap

           Index "public.page_daily_metrics_pkey"
 Column | Type | Key? | Definition | Storage | Stats target 
--------+------+------+------------+---------+--------------
 id     | uuid | yes  | id         | plain   | 
primary key, btree, for table "public.page_daily_metrics"

                                                         Table "public.pipeline_runs"
      Column      |           Type           | Collation | Nullable |      Default      | Storage  | Compression | Stats target | Description 
------------------+--------------------------+-----------+----------+-------------------+----------+-------------+--------------+-------------
 id               | uuid                     |           | not null | gen_random_uuid() | plain    |             |              | 
 account_id       | uuid                     |           | not null |                   | plain    |             |              | 
 is_running       | boolean                  |           |          | false             | plain    |             |              | 
 phase            | text                     |           |          | 'idle'::text      | extended |             |              | 
 current_step     | text                     |           |          |                   | extended |             |              | 
 progress_current | integer                  |           |          | 0                 | plain    |             |              | 
 progress_total   | integer                  |           |          | 0                 | plain    |             |              | 
 completed_steps  | text[]                   |           |          | '{}'::text[]      | extended |             |              | 
 error            | text                     |           |          |                   | extended |             |              | 
 started_at       | timestamp with time zone |           |          |                   | plain    |             |              | 
 completed_at     | timestamp with time zone |           |          |                   | plain    |             |              | 
 updated_at       | timestamp with time zone |           |          | now()             | plain    |             |              | 
Indexes:
    "pipeline_runs_pkey" PRIMARY KEY, btree (id)
    "idx_pipeline_runs_account" btree (account_id)
    "one_running_pipeline_per_account" UNIQUE, btree (account_id) WHERE is_running = true
Foreign-key constraints:
    "pipeline_runs_account_id_fkey" FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
Access method: heap

             Index "public.pipeline_runs_pkey"
 Column | Type | Key? | Definition | Storage | Stats target 
--------+------+------+------------+---------+--------------
 id     | uuid | yes  | id         | plain   | 
primary key, btree, for table "public.pipeline_runs"

                                                          Table "public.properties"
      Column      |           Type           | Collation | Nullable |      Default      | Storage  | Compression | Stats target | Description 
------------------+--------------------------+-----------+----------+-------------------+----------+-------------+--------------+-------------
 id               | uuid                     |           | not null | gen_random_uuid() | plain    |             |              | 
 website_id       | uuid                     |           | not null |                   | plain    |             |              | 
 site_url         | text                     |           | not null |                   | extended |             |              | 
 property_type    | text                     |           | not null |                   | extended |             |              | 
 permission_level | text                     |           | not null |                   | extended |             |              | 
 created_at       | timestamp with time zone |           |          | now()             | plain    |             |              | 
 account_id       | uuid                     |           | not null |                   | plain    |             |              | 
Indexes:
    "properties_pkey" PRIMARY KEY, btree (id)
    "idx_properties_account" btree (account_id)
    "properties_account_siteurl_unique" UNIQUE, btree (account_id, site_url)
Foreign-key constraints:
    "properties_account_id_fkey" FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
    "properties_website_id_fkey" FOREIGN KEY (website_id) REFERENCES websites(id) ON DELETE CASCADE
Referenced by:
    TABLE "alert_subscriptions" CONSTRAINT "alert_subscriptions_property_id_fkey" FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
    TABLE "alerts" CONSTRAINT "alerts_property_fk" FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
    TABLE "device_daily_metrics" CONSTRAINT "device_daily_metrics_property_id_fkey" FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
    TABLE "page_daily_metrics" CONSTRAINT "page_daily_metrics_property_id_fkey" FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
    TABLE "property_daily_metrics" CONSTRAINT "property_daily_metrics_property_id_fkey" FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
Access method: heap

        Index "public.properties_account_siteurl_unique"
   Column   | Type | Key? | Definition | Storage  | Stats target 
------------+------+------+------------+----------+--------------
 account_id | uuid | yes  | account_id | plain    | 
 site_url   | text | yes  | site_url   | extended | 
unique, btree, for table "public.properties"

               Index "public.properties_pkey"
 Column | Type | Key? | Definition | Storage | Stats target 
--------+------+------+------------+---------+--------------
 id     | uuid | yes  | id         | plain   | 
primary key, btree, for table "public.properties"

                                                 Table "public.property_daily_metrics"
   Column    |           Type           | Collation | Nullable |      Default      | Storage | Compression | Stats target | Description 
-------------+--------------------------+-----------+----------+-------------------+---------+-------------+--------------+-------------
 id          | uuid                     |           | not null | gen_random_uuid() | plain   |             |              | 
 property_id | uuid                     |           | not null |                   | plain   |             |              | 
 date        | date                     |           | not null |                   | plain   |             |              | 
 clicks      | integer                  |           | not null |                   | plain   |             |              | 
 impressions | integer                  |           | not null |                   | plain   |             |              | 
 ctr         | numeric                  |           | not null |                   | main    |             |              | 
 position    | numeric                  |           | not null |                   | main    |             |              | 
 created_at  | timestamp with time zone |           |          | now()             | plain   |             |              | 
Indexes:
    "property_daily_metrics_pkey" PRIMARY KEY, btree (id)
    "idx_property_metrics_property_date" btree (property_id, date DESC)
    "idx_property_property_date" btree (property_id, date)
    "property_daily_metrics_property_id_date_key" UNIQUE CONSTRAINT, btree (property_id, date)
    "property_metrics_unique_day" UNIQUE, btree (property_id, date)
    "unique_property_metric" UNIQUE CONSTRAINT, btree (property_id, date)
Foreign-key constraints:
    "property_daily_metrics_property_id_fkey" FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
Access method: heap

         Index "public.property_daily_metrics_pkey"
 Column | Type | Key? | Definition | Storage | Stats target 
--------+------+------+------------+---------+--------------
 id     | uuid | yes  | id         | plain   | 
primary key, btree, for table "public.property_daily_metrics"

    Index "public.property_daily_metrics_property_id_date_key"
   Column    | Type | Key? | Definition  | Storage | Stats target 
-------------+------+------+-------------+---------+--------------
 property_id | uuid | yes  | property_id | plain   | 
 date        | date | yes  | date        | plain   | 
unique, btree, for table "public.property_daily_metrics"

            Index "public.property_metrics_unique_day"
   Column    | Type | Key? | Definition  | Storage | Stats target 
-------------+------+------+-------------+---------+--------------
 property_id | uuid | yes  | property_id | plain   | 
 date        | date | yes  | date        | plain   | 
unique, btree, for table "public.property_daily_metrics"

         Index "public.recipients_account_email_unique"
   Column   | Type | Key? | Definition | Storage  | Stats target 
------------+------+------+------------+----------+--------------
 account_id | uuid | yes  | account_id | plain    | 
 email      | text | yes  | email      | extended | 
unique, btree, for table "public.alert_recipients"

              Index "public.unique_alert_recipient"
   Column   | Type | Key? | Definition | Storage  | Stats target 
------------+------+------+------------+----------+--------------
 account_id | uuid | yes  | account_id | plain    | 
 email      | text | yes  | email      | extended | 
unique, btree, for table "public.alert_recipients"

             Index "public.unique_alert_subscription"
   Column    | Type | Key? | Definition  | Storage  | Stats target 
-------------+------+------+-------------+----------+--------------
 account_id  | uuid | yes  | account_id  | plain    | 
 email       | text | yes  | email       | extended | 
 property_id | uuid | yes  | property_id | plain    | 
unique, btree, for table "public.alert_subscriptions"

                Index "public.unique_device_metric"
   Column    | Type | Key? | Definition  | Storage  | Stats target 
-------------+------+------+-------------+----------+--------------
 property_id | uuid | yes  | property_id | plain    | 
 device      | text | yes  | device      | extended | 
 date        | date | yes  | date        | plain    | 
unique, btree, for table "public.device_daily_metrics"

                  Index "public.unique_page_day"
   Column    | Type | Key? | Definition  | Storage  | Stats target 
-------------+------+------+-------------+----------+--------------
 property_id | uuid | yes  | property_id | plain    | 
 page_url    | text | yes  | page_url    | extended | 
 date        | date | yes  | date        | plain    | 
unique, btree, for table "public.page_daily_metrics"

              Index "public.unique_property_metric"
   Column    | Type | Key? | Definition  | Storage | Stats target 
-------------+------+------+-------------+---------+--------------
 property_id | uuid | yes  | property_id | plain   | 
 date        | date | yes  | date        | plain   | 
unique, btree, for table "public.property_daily_metrics"

                                                      Table "public.users"
   Column   |            Type             | Collation | Nullable | Default | Storage  | Compression | Stats target | Description 
------------+-----------------------------+-----------+----------+---------+----------+-------------+--------------+-------------
 id         | uuid                        |           | not null |         | plain    |             |              | 
 email      | text                        |           | not null |         | extended |             |              | 
 full_name  | text                        |           |          |         | extended |             |              | 
 created_at | timestamp without time zone |           |          | now()   | plain    |             |              | 
Indexes:
    "users_pkey" PRIMARY KEY, btree (id)
    "users_email_key" UNIQUE CONSTRAINT, btree (email)
Foreign-key constraints:
    "users_id_fkey" FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE
Access method: heap

               Index "public.users_email_key"
 Column | Type | Key? | Definition | Storage  | Stats target 
--------+------+------+------------+----------+--------------
 email  | text | yes  | email      | extended | 
unique, btree, for table "public.users"

                 Index "public.users_pkey"
 Column | Type | Key? | Definition | Storage | Stats target 
--------+------+------+------------+---------+--------------
 id     | uuid | yes  | id         | plain   | 
primary key, btree, for table "public.users"

                                                         Table "public.websites"
    Column    |           Type           | Collation | Nullable |      Default      | Storage  | Compression | Stats target | Description 
--------------+--------------------------+-----------+----------+-------------------+----------+-------------+--------------+-------------
 id           | uuid                     |           | not null | gen_random_uuid() | plain    |             |              | 
 base_domain  | text                     |           | not null |                   | extended |             |              | 
 display_name | text                     |           | not null |                   | extended |             |              | 
 created_at   | timestamp with time zone |           |          | now()             | plain    |             |              | 
 account_id   | uuid                     |           | not null |                   | plain    |             |              | 
Indexes:
    "websites_pkey" PRIMARY KEY, btree (id)
    "idx_websites_account" btree (account_id)
    "websites_account_domain_unique" UNIQUE, btree (account_id, base_domain)
Foreign-key constraints:
    "websites_account_id_fkey" FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
Referenced by:
    TABLE "properties" CONSTRAINT "properties_website_id_fkey" FOREIGN KEY (website_id) REFERENCES websites(id) ON DELETE CASCADE
Access method: heap

           Index "public.websites_account_domain_unique"
   Column    | Type | Key? | Definition  | Storage  | Stats target 
-------------+------+------+-------------+----------+--------------
 account_id  | uuid | yes  | account_id  | plain    | 
 base_domain | text | yes  | base_domain | extended | 
unique, btree, for table "public.websites"

                Index "public.websites_pkey"
 Column | Type | Key? | Definition | Storage | Stats target 
--------+------+------+------------+---------+--------------
 id     | uuid | yes  | id         | plain   | 
primary key, btree, for table "public.websites"

